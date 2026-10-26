"""IssueBot command-line interface."""

import logging
from pathlib import Path

import typer

from issuebot import __version__
from issuebot.agent.loop import solve_task
from issuebot.config import get_settings
from issuebot.models import RunStatus, Task
from issuebot.observability.tracing import Tracer

app = typer.Typer(help="IssueBot: a sandboxed issue-to-PR coding agent.", no_args_is_help=True)

# Benchmark sub-app
benchmark_app = typer.Typer(help="Run and report on the IssueBot benchmark suite.")
app.add_typer(benchmark_app, name="benchmark")


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def solve(
    repo: Path = typer.Option(..., "--repo", exists=True, file_okay=False, help="Repo path"),
    issue: str | None = typer.Option(None, "--issue", help="Issue text"),
    issue_file: Path | None = typer.Option(None, "--issue-file", exists=True),
    title: str = typer.Option("Bug report", "--title"),
    test_command: str = typer.Option("pytest -x -q", "--test-command"),
    max_steps: int | None = typer.Option(None, "--max-steps"),
    max_cost_usd: float | None = typer.Option(None, "--max-cost-usd"),
    model: str | None = typer.Option(None, "--model", help="Override STRONG_MODEL"),
    out: Path | None = typer.Option(None, "--out", help="Write the patch here"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fix a bug in REPO described by --issue / --issue-file."""
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
    settings = get_settings()
    if issue_file is not None:
        issue = issue_file.read_text(encoding="utf-8")
    if not issue:
        typer.echo("Provide --issue or --issue-file.", err=True)
        raise typer.Exit(2)
    from issuebot.llm import create_llm_client

    try:
        llm = create_llm_client(model, settings)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e
    task = Task(
        task_id=repo.resolve().name,
        repo_path=repo,
        issue_title=title,
        issue_body=issue,
        test_command=test_command,
        max_steps=max_steps or settings.max_steps,
        max_cost_usd=max_cost_usd or settings.max_cost_usd,
        max_wall_seconds=settings.max_wall_seconds,
    )
    import uuid

    run_id = uuid.uuid4().hex[:12]
    trace_path = Path(settings.runs_dir) / run_id / "trace.jsonl"
    result = solve_task(task, llm, tracer=Tracer(trace_path), run_id=run_id)

    typer.echo(f"Run {result.run_id}: {result.status.value}")
    typer.echo(
        f"Steps: {len(result.steps)}  Cost: ${result.total_cost_usd:.4f}  "
        f"Time: {result.wall_seconds:.1f}s  Trace: {trace_path}"
    )
    if result.explanation:
        typer.echo(f"\nSummary: {result.explanation}")
    if result.patch:
        if out:
            out.write_text(result.patch, encoding="utf-8")
            typer.echo(f"\nPatch written to {out}")
        else:
            typer.echo("\n" + result.patch)
    raise typer.Exit(0 if result.status == RunStatus.SOLVED else 1)


# ─── Benchmark commands ───────────────────────────────────────────────────────


@benchmark_app.command("run")
def benchmark_run(
    examples_dir: Path = typer.Option(
        Path("examples"),
        "--examples-dir",
        exists=True,
        file_okay=False,
        help="Directory containing seed repo sub-dirs",
    ),
    task_ids: list[str] = typer.Option(
        [],
        "--task",
        help="Run only these task IDs (repeat for multiple); default: all",
    ),
    model: str | None = typer.Option(None, "--model", help="Override STRONG_MODEL"),
    max_steps: int = typer.Option(25, "--max-steps"),
    max_cost_usd: float = typer.Option(0.50, "--max-cost-usd"),
    out_dir: Path = typer.Option(Path("runs/benchmark"), "--out-dir"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Use scripted mock LLM (no API calls, for CI smoke tests)",
    ),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Apply patches and re-run tests for ground-truth validation",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the agent on every seed repo and produce a benchmark report."""
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
    settings = get_settings()

    from issuebot.benchmark.loader import load_tasks
    from issuebot.benchmark.reporter import build_metrics, build_report, write_jsonl, write_report
    from issuebot.benchmark.runner import run_benchmark
    from issuebot.benchmark.validator import validate_all
    from issuebot.llm.base import LLMClient

    tasks = load_tasks(
        examples_dir,
        task_ids=list(task_ids) or None,
        max_steps=max_steps,
        max_cost_usd=max_cost_usd,
        max_wall_seconds=settings.max_wall_seconds,
    )
    if not tasks:
        typer.echo("No tasks found. Check --examples-dir.", err=True)
        raise typer.Exit(2)

    typer.echo(f"Found {len(tasks)} tasks: {[t.task_id for t in tasks]}")

    llm: LLMClient
    if dry_run:
        from issuebot.llm.mock import MockLLMClient

        llm = MockLLMClient()
        typer.echo("[dry-run] Using MockLLMClient (no API calls)")
    else:
        from issuebot.llm import create_llm_client

        try:
            llm = create_llm_client(model, settings)
        except ValueError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(2) from e

    results = run_benchmark(tasks, llm, runs_dir=out_dir / "traces", verbose=verbose)

    validations = validate_all(tasks, results) if validate else []

    metrics = build_metrics(results, validations)
    metrics_path = out_dir / "metrics.jsonl"
    write_jsonl(metrics, metrics_path)
    typer.echo(f"\nMetrics written to {metrics_path}")

    report = build_report(results, validations, model=llm.model)
    report_path = out_dir / "report.md"
    write_report(report, report_path)
    typer.echo(f"Report written to {report_path}")

    typer.echo("\n" + report)

    n_genuine = sum(1 for v in validations if v.is_genuine_fix)
    n_total = len(results)
    raise typer.Exit(0 if n_genuine == n_total else 1)


@benchmark_app.command("report")
def benchmark_report(
    metrics_file: Path = typer.Argument(
        ..., exists=True, help="Path to a metrics.jsonl file from a previous run"
    ),
    out: Path | None = typer.Option(None, "--out", help="Write Markdown report here"),
) -> None:
    """Re-generate a Markdown report from an existing metrics.jsonl file."""
    import json as _json

    from issuebot.benchmark.reporter import build_report, write_report
    from issuebot.models import RunResult, RunStatus

    rows = [_json.loads(line) for line in metrics_file.read_text().splitlines() if line.strip()]

    # Reconstruct minimal RunResult objects from metrics rows
    results: list[RunResult] = []
    for row in rows:
        results.append(
            RunResult(
                run_id=row.get("run_id", row["task_id"]),
                task_id=row["task_id"],
                status=RunStatus(row["agent_status"]),
                patch=None,
                steps=[],
                total_input_tokens=row.get("input_tokens", 0),
                total_output_tokens=row.get("output_tokens", 0),
                total_cost_usd=row.get("cost_usd", 0.0),
                wall_seconds=row.get("wall_seconds", 0.0),
                model_config_name=row.get("model", "unknown"),
                explanation=row.get("explanation"),
                hidden_tests_passed=row.get("hidden_tests_passed"),
            )
        )

    model = rows[0].get("model", "unknown") if rows else "unknown"
    report = build_report(results, [], model=model)

    if out:
        write_report(report, out)
        typer.echo(f"Report written to {out}")
    else:
        typer.echo(report)


if __name__ == "__main__":
    app()

