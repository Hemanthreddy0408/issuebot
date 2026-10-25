from pathlib import Path

import pytest

from issuebot.models import Task

SEED = Path(__file__).resolve().parents[1] / "examples" / "seed_cart"


@pytest.fixture
def seed_repo() -> Path:
    return SEED


@pytest.fixture
def task(seed_repo: Path) -> Task:
    return Task(
        task_id="seed_cart",
        repo_path=seed_repo,
        issue_title="Bulk discount missing at exactly 10",
        issue_body=(seed_repo / "ISSUE.md").read_text(),
        test_command="pytest -x -q",
    )
