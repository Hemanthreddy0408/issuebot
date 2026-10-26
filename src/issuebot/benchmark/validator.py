"""Benchmark validator.

Validates a RunResult against the ground-truth: runs the full test suite on
the agent's patch applied to a fresh copy of the repo. This is more strict
than the agent's own ``finish`` verification because it uses **all** tests,
not just ``pytest -x -q``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from issuebot.models import RunResult, RunStatus, Task


@dataclass
class ValidationResult:
    task_id: str
    agent_status: RunStatus
    patch_applies: bool | None  # None when status is not solved
    full_suite_passed: bool | None  # None when patch didn't apply
    hidden_tests_passed: bool | None  # None when no hidden test command
    notes: str = ""

    @property
    def is_genuine_fix(self) -> bool:
        """True only when every validation gate passed."""
        return (
            self.agent_status == RunStatus.SOLVED
            and self.patch_applies is True
            and self.full_suite_passed is True
            and (self.hidden_tests_passed is None or self.hidden_tests_passed is True)
        )


def validate_result(task: Task, result: RunResult) -> ValidationResult:
    """Apply the agent's patch and run the full test suite.

    This is separate from the hidden-test runner: it runs the *visible* test
    suite with ``pytest`` (no ``-x`` flag so all failures are reported) against
    the patched repo. It gives a definitive "does the fix actually work?" answer.
    """
    if result.status != RunStatus.SOLVED or not result.patch:
        return ValidationResult(
            task_id=task.task_id,
            agent_status=result.status,
            patch_applies=None,
            full_suite_passed=None,
            hidden_tests_passed=result.hidden_tests_passed,
            notes="Agent did not produce a patch.",
        )

    tmp = Path(tempfile.mkdtemp(prefix="issuebot_validate_"))
    try:
        dest = tmp / task.task_id
        shutil.copytree(task.repo_path, dest, dirs_exist_ok=True)

        # Apply patch
        patch_file = tmp / "agent.patch"
        patch_file.write_text(result.patch, encoding="utf-8")
        patch_proc = subprocess.run(
            ["patch", "-p1", "--input", str(patch_file)],
            check=False,
            cwd=dest,
            capture_output=True,
            text=True,
        )
        if patch_proc.returncode != 0:
            return ValidationResult(
                task_id=task.task_id,
                agent_status=result.status,
                patch_applies=False,
                full_suite_passed=None,
                hidden_tests_passed=result.hidden_tests_passed,
                notes=f"patch failed: {patch_proc.stderr[:500]}",
            )

        # Run full visible test suite (no -x so we see all failures)
        test_cmd = task.test_command.replace("-x", "").split()
        if "-q" not in test_cmd:
            test_cmd.append("-q")
        proc = subprocess.run(
            test_cmd,
            check=False,
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=task.max_wall_seconds,
        )
        full_suite_passed = proc.returncode == 0
        notes = "" if full_suite_passed else proc.stdout[-1000:] + proc.stderr[-500:]

        return ValidationResult(
            task_id=task.task_id,
            agent_status=result.status,
            patch_applies=True,
            full_suite_passed=full_suite_passed,
            hidden_tests_passed=result.hidden_tests_passed,
            notes=notes.strip(),
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            task_id=task.task_id,
            agent_status=result.status,
            patch_applies=True,
            full_suite_passed=False,
            hidden_tests_passed=result.hidden_tests_passed,
            notes="Full-suite validation timed out.",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def validate_all(
    tasks: list[Task],
    results: list[RunResult],
) -> list[ValidationResult]:
    """Validate every (task, result) pair. Tasks and results must be same-order."""
    task_map = {t.task_id: t for t in tasks}
    validations: list[ValidationResult] = []
    for result in results:
        task = task_map.get(result.task_id)
        if task is None:
            continue
        validations.append(validate_result(task, result))
    return validations
