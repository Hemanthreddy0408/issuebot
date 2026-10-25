"""Tool schemas and the tool executor."""

import hashlib
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from issuebot.agent.context import truncate
from issuebot.models import ToolCall, ToolResult
from issuebot.repo.workspace import Workspace
from issuebot.sandbox.docker_runner import DockerSandboxError, DockerSandboxRunner
from issuebot.security.command_policy import CommandPolicy, CommandPolicyError
from issuebot.security.path_guard import PathGuard, PathGuardError
from issuebot.security.secrets import redact_secrets

logger = logging.getLogger(__name__)

MAX_READ_LINES = 300

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_code",
        "description": "Regex/keyword search over the repo; also matches function/class names. "
        "Returns path:line: snippet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read numbered lines of a file (max 300 lines per call). "
        "Path is relative to the repo root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "default": 1},
                "end_line": {"type": "integer", "default": 200},
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace one exact occurrence of old_str with new_str. old_str must "
        "appear exactly once. If old_str is empty and the file does not exist, creates it "
        "with new_str as content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
    {
        "name": "run_tests",
        "description": "Run the test suite (pytest only). Returns a summarized result.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "path": {"type": "string"}},
        },
    },
    {
        "name": "git_diff",
        "description": "Show the current unified diff of your changes.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "finish",
        "description": "Declare you are done. The system will run the tests one final time.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


class ToolError(Exception):
    """A recoverable tool failure whose message is shown to the model."""


class ToolExecutor:
    """Executes tool calls against a Workspace."""

    def __init__(
        self,
        workspace: Workspace,
        default_test_command: str,
        test_timeout: int = 60,
        sandbox_runner: DockerSandboxRunner | None = None,
        use_docker: bool = True,
    ) -> None:
        self.ws = workspace
        self.default_test_command = default_test_command
        self.test_timeout = test_timeout
        self.path_guard = PathGuard(workspace.root)

        from issuebot.config import get_settings

        settings = get_settings()
        self.use_docker = use_docker and settings.use_docker_sandbox
        self.sandbox_runner = sandbox_runner or DockerSandboxRunner(
            image=settings.sandbox_image,
            mem_limit=f"{settings.sandbox_mem_mb}m",
            nano_cpus=int(settings.sandbox_cpus * 1_000_000_000),
            timeout_seconds=test_timeout,
        )

        self.has_explored = False
        self.edit_count = 0
        self.last_test_digest = ""
        self.last_test_passed: bool | None = None
        self.last_raw_test_output = ""

    # ---------------------------------------------------------------- dispatch
    def execute(self, call: ToolCall) -> ToolResult:
        """Run a tool call; never raises."""
        handlers: dict[str, Callable[..., str]] = {
            "search_code": self._search_code,
            "read_file": self._read_file,
            "edit_file": self._edit_file,
            "run_tests": self._run_tests,
            "git_diff": self._git_diff,
        }
        handler = handlers.get(call.name)
        try:
            if handler is None:
                raise ToolError(f"Unknown tool {call.name!r}. Valid: {sorted(handlers)} + finish")
            output = handler(**call.arguments)
            ok = True
        except (ToolError, CommandPolicyError, PathGuardError) as e:
            output, ok = f"ERROR: {e}", False
        except TypeError as e:
            output, ok = f"ERROR: invalid arguments: {e}", False
        except Exception as e:
            logger.exception("Tool %s crashed", call.name)
            output, ok = f"ERROR: internal tool error: {type(e).__name__}", False

        # Redact secrets from all tool outputs
        cleaned = redact_secrets(output)
        text, was_truncated = truncate(cleaned)
        return ToolResult(tool_call_id=call.id, ok=ok, output=text, truncated=was_truncated)

    # ------------------------------------------------------------------- paths
    def _resolve(self, rel: str, *, for_write: bool = False) -> Path:
        return self.path_guard.resolve_safe(rel, for_write=for_write)

    # ------------------------------------------------------------------- tools
    def _search_code(self, query: str, max_results: int = 20) -> str:
        max_results = max(1, min(int(max_results), 100))
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        results: list[str] = []
        q = query.strip().lower()
        for s in self.ws.symbols():
            if q and q in s.name.lower():
                results.append(f"{s.path}:{s.line}: [{s.kind}] {s.name}")
        for f in self.ws.iter_files():
            try:
                lines = (self.ws.root / f).read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    results.append(f"{f}:{i}: {line.strip()[:200]}")
        self.has_explored = True
        if not results:
            return "No matches."
        shown = results[:max_results]
        hidden = len(results) - max_results
        extra = f"\n... {hidden} more matches" if hidden > 0 else ""
        return "\n".join(shown) + extra

    def _read_file(self, path: str, start_line: int = 1, end_line: int = 200) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise ToolError(f"File not found: {path}")
        data = target.read_bytes()
        if b"\0" in data:
            raise ToolError("Binary files cannot be read")
        lines = data.decode("utf-8", errors="replace").splitlines()
        start = max(1, int(start_line))
        end = min(int(end_line), start + MAX_READ_LINES - 1, len(lines))
        if start > len(lines):
            raise ToolError(f"start_line {start} is past the end of the file ({len(lines)} lines)")
        body = "\n".join(f"{i:>5}\t{lines[i - 1]}" for i in range(start, end + 1))
        self.has_explored = True
        return f"{path} (lines {start}-{end} of {len(lines)})\n{body}"

    def _edit_file(self, path: str, old_str: str, new_str: str) -> str:
        if not self.has_explored:
            raise ToolError(
                "Before editing, explore the repo with search_code or read_file, "
                "and state a short plan."
            )
        target = self._resolve(path, for_write=True)
        if old_str == "":
            if target.exists():
                raise ToolError("old_str is empty but the file already exists")
            self.path_guard.validate_test_integrity(target, "", new_str)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_str, encoding="utf-8")
            self.edit_count += 1
            return f"Created {path}"
        if not target.is_file():
            raise ToolError(f"File not found: {path}")
        text = target.read_text(encoding="utf-8")
        count = text.count(old_str)
        if count == 0:
            raise ToolError("old_str was not found in the file (must match exactly)")
        if count > 1:
            raise ToolError(f"old_str appears {count} times; include more context to be unique")
        new_text = text.replace(old_str, new_str, 1)
        # Validate that existing test assertions are not deleted or weakened
        self.path_guard.validate_test_integrity(target, text, new_text)
        target.write_text(new_text, encoding="utf-8")
        self.edit_count += 1
        return f"Edited {path} (1 replacement)"

    def _git_diff(self) -> str:
        return self.ws.diff() or "(no changes)"

    def _run_tests(self, command: str = "", path: str = "") -> str:
        _, summary = self.run_tests_raw(command or None, path)
        return summary

    # ------------------------------------------------------------- test runner
    def _run_local_subprocess(self, argv: list[str]) -> tuple[str, bool, int]:
        """Fallback local subprocess execution when Docker is unavailable or disabled."""
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": str(self.ws.root),
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-m", *argv],
                check=False,
                cwd=self.ws.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
            )
            raw = (proc.stdout or "") + (proc.stderr or "")
            passed = proc.returncode == 0
            code = proc.returncode
        except subprocess.TimeoutExpired as e:
            raw = f"Test run timed out after {self.test_timeout}s\n" + str(e.stdout or "")
            passed, code = False, -1
        return raw, passed, code

    def run_tests_raw(self, command: str | None = None, path: str = "") -> tuple[bool, str]:
        """Run tests; returns (passed, summarized_output). Raises ToolError on bad command."""
        cmd_str = command or self.default_test_command
        try:
            argv = CommandPolicy.validate_and_parse(cmd_str, path)
        except CommandPolicyError as e:
            raise ToolError(str(e)) from e

        if self.use_docker and self.sandbox_runner.is_docker_available():
            try:
                res = self.sandbox_runner.run(self.ws.root, argv, timeout=self.test_timeout)
                raw = res.output
                passed = res.exit_code == 0
                code = res.exit_code
            except DockerSandboxError as e:
                logger.warning("Docker sandbox failed (%s); falling back to local runner", e)
                raw, passed, code = self._run_local_subprocess(argv)
        else:
            raw, passed, code = self._run_local_subprocess(argv)

        self.last_raw_test_output = raw
        self.last_test_passed = passed
        self.last_test_digest = hashlib.sha256(raw.encode()).hexdigest()
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        last = lines[-1] if lines else "(no output)"
        if passed:
            return True, f"Tests PASSED: {last}"
        tail = "\n".join(lines[-60:])
        return False, f"Tests FAILED (exit code {code}): {last}\n--- output tail ---\n{tail}"
