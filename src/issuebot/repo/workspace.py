"""Temporary workspace: an editable copy of the repo plus a pristine snapshot for diffing."""

import ast
import difflib
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "node_modules",
}


_BINARY = "\0binary\0"


@dataclass(frozen=True)
class Symbol:
    """A function or class definition."""

    name: str
    kind: str
    path: str
    line: int


class Workspace:
    """An isolated copy of a repo. Never touches the original repo."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.root = base / "work"
        self.original = base / "orig"

    @classmethod
    def create(cls, repo_path: Path) -> "Workspace":
        """Copy `repo_path` into a fresh temp directory (twice: work + pristine)."""
        repo_path = Path(repo_path)
        if not repo_path.is_dir():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
        base = Path(tempfile.mkdtemp(prefix="issuebot_"))
        ignore = shutil.ignore_patterns(*IGNORE_DIRS)
        shutil.copytree(repo_path, base / "work", ignore=ignore)
        shutil.copytree(repo_path, base / "orig", ignore=ignore)
        return cls(base)

    def cleanup(self) -> None:
        """Delete the temp directory."""
        shutil.rmtree(self.base, ignore_errors=True)

    @staticmethod
    def _iter(root: Path) -> Iterator[str]:
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
            if p.is_file() and not p.is_symlink():
                yield rel.as_posix()

    def iter_files(self) -> Iterator[str]:
        """Yield workspace-relative file paths (posix style)."""
        return self._iter(self.root)

    def tree(self, max_entries: int = 150) -> str:
        """Compact, capped listing of files."""
        files = list(self.iter_files())
        shown = files[:max_entries]
        out = "\n".join(shown)
        if len(files) > max_entries:
            out += f"\n... ({len(files) - max_entries} more files)"
        return out or "(empty repository)"

    def test_files(self) -> list[str]:
        """Files that look like tests."""
        result = []
        for f in self.iter_files():
            p = Path(f)
            if f.endswith(".py") and (
                p.name.startswith("test_") or p.name.endswith("_test.py") or "tests" in p.parts
            ):
                result.append(f)
        return result

    def symbols(self) -> list[Symbol]:
        """Build a function/class index from Python files using `ast`."""
        found: list[Symbol] = []
        for f in self.iter_files():
            if not f.endswith(".py"):
                continue
            try:
                tree = ast.parse((self.root / f).read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, ValueError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    found.append(Symbol(node.name, "function", f, node.lineno))
                elif isinstance(node, ast.ClassDef):
                    found.append(Symbol(node.name, "class", f, node.lineno))
        return found

    @staticmethod
    def _read_lines(path: Path) -> list[str] | None:
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return [_BINARY]
        lines = text.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n\\ No newline at end of file\n"
        return lines

    def diff(self) -> str:
        """Unified diff of the workspace against the pristine snapshot."""
        names = sorted(set(self._iter(self.root)) | set(self._iter(self.original)))
        chunks: list[str] = []
        for name in names:
            old = self._read_lines(self.original / name)
            new = self._read_lines(self.root / name)
            if old == new or _BINARY in (old or []) or _BINARY in (new or []):
                continue
            chunks.extend(
                difflib.unified_diff(
                    old or [],
                    new or [],
                    fromfile=f"a/{name}" if old is not None else "/dev/null",
                    tofile=f"b/{name}" if new is not None else "/dev/null",
                )
            )
        return "".join(chunks)
