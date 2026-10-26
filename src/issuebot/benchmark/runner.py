"""Benchmark runner.

Runs the agent on a list of Tasks, collecting RunResult objects.
Supports an optional post-run hidden-test validation step.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from issuebot.agent.loop import solve_task
from issuebot.llm.base import LLMClient
from issuebot.models import RunResult, Task
from issuebot.observability.tracing import Tracer

logger = logging.getLogger(__name__)


def _apply_patch_and_run_hidden_tests(
    task: Task,
    result: RunResult,
) -> bool | None:
    """Apply agent patch to a fresh copy of the repo, run hidden tests.

    Returns True/False/None (None = no hidden test command configured).
    """
    if not task.hidden_test_command:
        return None
    if not result.patch:
        return False

    tmp = Path(tempfile.mkdtemp(prefix="issuebot_hidden_"))
    try:
        # Copy original repo
        dest = tmp / task.task_id
        shutil.copytree(task.repo_path, dest, dirs_exist_ok=True)

        # Apply the unified diff via `patch`
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
            logger.warning(
                "Task %s: patch failed:\n%s", task.task_id, patch_proc.stderr
            )
            return False

        # Run hidden tests
        cmd = task.hidden_test_command.split()
        proc = subprocess.run(
            cmd,
            check=False,
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=task.max_wall_seconds,
        )
        passed = proc.returncode == 0
        logger.info(
            "Task %s hidden tests: %s", task.task_id, "PASS" if passed else "FAIL"
        )
        return passed
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("Task %s: hidden test error: %s", task.task_id, exc)
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_benchmark(
    tasks: list[Task],
    llm: LLMClient,
    runs_dir: Path,
    *,
    verbose: bool = False,
) -> list[RunResult]:
    """Run all *tasks* sequentially and return results.

    Parameters
    ----------
    tasks:
        List of Task objects (from ``benchmark.loader.load_tasks``).
    llm:
        LLM client to use (MockLLMClient during dry-runs, AnthropicClient in live runs).
    runs_dir:
        Directory where trace JSONL files are written.
    verbose:
        If True, log INFO-level output.
    """
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )

    runs_dir.mkdir(parents=True, exist_ok=True)
    results: list[RunResult] = []

    for i, task in enumerate(tasks, 1):
        logger.info("[%d/%d] Running task %s", i, len(tasks), task.task_id)
        t0 = time.monotonic()

        trace_path = runs_dir / f"{task.task_id}_trace.jsonl"
        tracer = Tracer(trace_path)

        result = solve_task(task, llm, tracer=tracer, run_id=task.task_id)

        # Optional hidden-test validation
        hidden_passed = _apply_patch_and_run_hidden_tests(task, result)
        result = result.model_copy(update={"hidden_tests_passed": hidden_passed})

        results.append(result)
        elapsed = time.monotonic() - t0
        logger.info(
            "Task %s done in %.1fs: %s (cost=$%.4f)",
            task.task_id,
            elapsed,
            result.status.value,
            result.total_cost_usd,
        )

    return results
