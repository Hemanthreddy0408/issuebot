"""Tests for the benchmark package (loader, reporter, validator stubs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from issuebot.benchmark.loader import load_tasks
from issuebot.benchmark.reporter import build_metrics, build_report, write_jsonl
from issuebot.benchmark.validator import ValidationResult, validate_all
from issuebot.models import RunResult, RunStatus, Task

# ─── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def examples_dir(tmp_path: Path) -> Path:
    """Create a minimal examples directory with two seed repos."""
    for name, issue, cmd in [
        ("seed_alpha", "Fix the off-by-one in alpha.py.", "pytest -x -q"),
        ("seed_beta", "Fix the logic error in beta.py.", "pytest -x -q"),
    ]:
        repo = tmp_path / name
        repo.mkdir()
        (repo / "ISSUE.md").write_text(issue, encoding="utf-8")
        (repo / "ISSUE_TITLE.txt").write_text(f"{name} bug", encoding="utf-8")
        if cmd != "pytest -x -q":
            (repo / "TEST_COMMAND.txt").write_text(cmd, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def solved_result() -> RunResult:
    return RunResult(
        run_id="abc123",
        task_id="seed_alpha",
        status=RunStatus.SOLVED,
        patch="--- a/alpha.py\n+++ b/alpha.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
        steps=[],
        total_input_tokens=1000,
        total_output_tokens=200,
        total_cost_usd=0.005,
        wall_seconds=12.5,
        model_config_name="claude-test",
        explanation="Fixed the off-by-one error.",
    )


@pytest.fixture()
def failed_result() -> RunResult:
    return RunResult(
        run_id="def456",
        task_id="seed_beta",
        status=RunStatus.FAILED_TESTS,
        patch=None,
        steps=[],
        total_input_tokens=500,
        total_output_tokens=100,
        total_cost_usd=0.002,
        wall_seconds=8.0,
        model_config_name="claude-test",
        explanation="Could not fix the tests.",
    )


# ─── loader tests ─────────────────────────────────────────────────────────────


def test_load_tasks_discovers_seed_repos(examples_dir: Path) -> None:
    tasks = load_tasks(examples_dir)
    assert len(tasks) == 2
    ids = {t.task_id for t in tasks}
    assert ids == {"seed_alpha", "seed_beta"}


def test_load_tasks_reads_issue_body(examples_dir: Path) -> None:
    tasks = load_tasks(examples_dir)
    alpha = next(t for t in tasks if t.task_id == "seed_alpha")
    assert "off-by-one" in alpha.issue_body


def test_load_tasks_reads_title(examples_dir: Path) -> None:
    tasks = load_tasks(examples_dir)
    alpha = next(t for t in tasks if t.task_id == "seed_alpha")
    assert alpha.issue_title == "seed_alpha bug"


def test_load_tasks_default_title_from_dir_name(tmp_path: Path) -> None:
    repo = tmp_path / "my_cool_repo"
    repo.mkdir()
    (repo / "ISSUE.md").write_text("some issue", encoding="utf-8")
    tasks = load_tasks(tmp_path)
    assert tasks[0].issue_title == "My Cool Repo"


def test_load_tasks_filter_by_id(examples_dir: Path) -> None:
    tasks = load_tasks(examples_dir, task_ids=["seed_alpha"])
    assert len(tasks) == 1
    assert tasks[0].task_id == "seed_alpha"


def test_load_tasks_budget_overrides(examples_dir: Path) -> None:
    tasks = load_tasks(examples_dir, max_steps=10, max_cost_usd=0.20)
    for t in tasks:
        assert t.max_steps == 10
        assert t.max_cost_usd == 0.20


def test_load_tasks_empty_dir(tmp_path: Path) -> None:
    tasks = load_tasks(tmp_path)
    assert tasks == []


def test_load_tasks_ignores_dirs_without_issue_md(tmp_path: Path) -> None:
    (tmp_path / "no_issue").mkdir()
    tasks = load_tasks(tmp_path)
    assert tasks == []


def test_load_tasks_custom_test_command(tmp_path: Path) -> None:
    repo = tmp_path / "seed_custom"
    repo.mkdir()
    (repo / "ISSUE.md").write_text("bug", encoding="utf-8")
    (repo / "TEST_COMMAND.txt").write_text("pytest tests/ -v", encoding="utf-8")
    tasks = load_tasks(tmp_path)
    assert tasks[0].test_command == "pytest tests/ -v"


# ─── reporter tests ───────────────────────────────────────────────────────────


def test_build_metrics_basic(solved_result: RunResult, failed_result: RunResult) -> None:
    metrics = build_metrics([solved_result, failed_result], [])
    assert len(metrics) == 2
    alpha = next(m for m in metrics if m["task_id"] == "seed_alpha")
    assert alpha["agent_status"] == "solved"
    assert alpha["cost_usd"] == pytest.approx(0.005, abs=1e-6)
    assert alpha["steps"] == 0


def test_build_metrics_genuine_fix_from_validation(
    solved_result: RunResult,
) -> None:
    vr = ValidationResult(
        task_id="seed_alpha",
        agent_status=RunStatus.SOLVED,
        patch_applies=True,
        full_suite_passed=True,
        hidden_tests_passed=None,
    )
    metrics = build_metrics([solved_result], [vr])
    assert metrics[0]["genuine_fix"] is True


def test_write_jsonl_creates_file(
    tmp_path: Path, solved_result: RunResult
) -> None:
    metrics = build_metrics([solved_result], [])
    out = tmp_path / "metrics.jsonl"
    write_jsonl(metrics, out)
    assert out.exists()
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[0]["task_id"] == "seed_alpha"


def test_build_report_contains_key_sections(
    solved_result: RunResult, failed_result: RunResult
) -> None:
    report = build_report([solved_result, failed_result], [], model="claude-test")
    assert "# IssueBot Benchmark Report" in report
    assert "## Summary" in report
    assert "## Per-task results" in report
    assert "## Failure analysis" in report
    assert "seed_alpha" in report
    assert "seed_beta" in report


def test_build_report_shows_genuine_fix_emoji(solved_result: RunResult) -> None:
    vr = ValidationResult(
        task_id="seed_alpha",
        agent_status=RunStatus.SOLVED,
        patch_applies=True,
        full_suite_passed=True,
        hidden_tests_passed=None,
    )
    report = build_report([solved_result], [vr], model="claude-test")
    assert "✅" in report


def test_build_report_all_solved(solved_result: RunResult) -> None:
    vr = ValidationResult(
        task_id="seed_alpha",
        agent_status=RunStatus.SOLVED,
        patch_applies=True,
        full_suite_passed=True,
        hidden_tests_passed=None,
    )
    report = build_report([solved_result], [vr], model="x")
    assert "🎉" in report


def test_build_report_failure_analysis(failed_result: RunResult) -> None:
    vr = ValidationResult(
        task_id="seed_beta",
        agent_status=RunStatus.FAILED_TESTS,
        patch_applies=None,
        full_suite_passed=None,
        hidden_tests_passed=None,
        notes="",
    )
    report = build_report([failed_result], [vr], model="x")
    assert "seed_beta" in report
    assert "failed_tests" in report


# ─── validator tests (unit-level, no subprocess) ──────────────────────────────


def test_validation_result_not_genuine_when_not_solved(failed_result: RunResult) -> None:
    vr = ValidationResult(
        task_id="seed_beta",
        agent_status=RunStatus.FAILED_TESTS,
        patch_applies=None,
        full_suite_passed=None,
        hidden_tests_passed=None,
    )
    assert not vr.is_genuine_fix


def test_validation_result_genuine_when_all_pass() -> None:
    vr = ValidationResult(
        task_id="x",
        agent_status=RunStatus.SOLVED,
        patch_applies=True,
        full_suite_passed=True,
        hidden_tests_passed=None,
    )
    assert vr.is_genuine_fix


def test_validation_result_not_genuine_when_patch_fails() -> None:
    vr = ValidationResult(
        task_id="x",
        agent_status=RunStatus.SOLVED,
        patch_applies=False,
        full_suite_passed=None,
        hidden_tests_passed=None,
    )
    assert not vr.is_genuine_fix


def test_validation_result_not_genuine_when_hidden_tests_fail() -> None:
    vr = ValidationResult(
        task_id="x",
        agent_status=RunStatus.SOLVED,
        patch_applies=True,
        full_suite_passed=True,
        hidden_tests_passed=False,
    )
    assert not vr.is_genuine_fix


def test_validate_all_skips_missing_task(solved_result: RunResult) -> None:
    tasks: list[Task] = []  # no matching task
    results = validate_all(tasks, [solved_result])
    assert results == []


# ─── CLI benchmark command smoke test ─────────────────────────────────────────


def test_benchmark_run_dry_run_cli(examples_dir: Path, tmp_path: Path) -> None:
    """Smoke-test `issuebot benchmark run --dry-run` using Typer's test runner."""
    from typer.testing import CliRunner

    from issuebot.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark",
            "run",
            "--examples-dir",
            str(examples_dir),
            "--dry-run",
            "--no-validate",
            "--out-dir",
            str(tmp_path / "bench_out"),
        ],
    )
    # dry-run with mock LLM always exits with code 0 or 1 (not a crash)
    assert result.exit_code in (0, 1), result.output
    assert "Found 2 tasks" in result.output
    assert "Metrics written" in result.output or "metrics.jsonl" in result.output
