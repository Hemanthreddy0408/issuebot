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
    if not settings.anthropic_api_key:
        typer.echo("ANTHROPIC_API_KEY is not set (see .env.example).", err=True)
        raise typer.Exit(2)

    from issuebot.llm.anthropic_client import AnthropicClient

    llm = AnthropicClient(model or settings.strong_model, settings.anthropic_api_key)
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


if __name__ == "__main__":
    app()
