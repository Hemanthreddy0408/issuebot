"""Benchmark task loader.

Discovers seed repos under an *examples_dir* directory.

A seed repo is a directory that contains an ``ISSUE.md`` file.
Optional files that can live next to ``ISSUE.md``:
  ``ISSUE_TITLE.txt``    – one-line title (defaults to the repo dir name)
  ``TEST_COMMAND.txt``   – override the default test command
  ``HIDDEN_TESTS/``      – extra tests copied in after the agent finishes to
                           measure true fix quality (not revealed to the agent)
"""

from __future__ import annotations

import logging
from pathlib import Path

from issuebot.models import Task

logger = logging.getLogger(__name__)

DEFAULT_TEST_COMMAND = "pytest -x -q"


def load_tasks(
    examples_dir: Path,
    *,
    task_ids: list[str] | None = None,
    max_steps: int = 25,
    max_cost_usd: float = 0.50,
    max_wall_seconds: int = 600,
) -> list[Task]:
    """Return a list of Tasks discovered under *examples_dir*.

    Parameters
    ----------
    examples_dir:
        Directory that contains one sub-directory per seed repo.
    task_ids:
        If given, only tasks whose ID is in this list are returned.
    max_steps, max_cost_usd, max_wall_seconds:
        Budget overrides applied to every task.
    """
    tasks: list[Task] = []
    for repo_dir in sorted(examples_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        issue_path = repo_dir / "ISSUE.md"
        if not issue_path.exists():
            continue

        task_id = repo_dir.name
        if task_ids and task_id not in task_ids:
            continue

        title_path = repo_dir / "ISSUE_TITLE.txt"
        title = (
            title_path.read_text(encoding="utf-8").strip()
            if title_path.exists()
            else task_id.replace("_", " ").replace("-", " ").title()
        )

        cmd_path = repo_dir / "TEST_COMMAND.txt"
        test_command = (
            cmd_path.read_text(encoding="utf-8").strip()
            if cmd_path.exists()
            else DEFAULT_TEST_COMMAND
        )

        hidden_cmd_path = repo_dir / "HIDDEN_TEST_COMMAND.txt"
        hidden_test_command: str | None = (
            hidden_cmd_path.read_text(encoding="utf-8").strip()
            if hidden_cmd_path.exists()
            else None
        )

        issue_body = issue_path.read_text(encoding="utf-8")

        task = Task(
            task_id=task_id,
            repo_path=repo_dir,
            issue_title=title,
            issue_body=issue_body,
            test_command=test_command,
            hidden_test_command=hidden_test_command,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
            max_wall_seconds=max_wall_seconds,
        )
        tasks.append(task)
        logger.debug("Loaded task %s from %s", task_id, repo_dir)

    if not tasks:
        logger.warning("No seed repos found under %s", examples_dir)
    return tasks
