"""Benchmark reporter.

Produces:
  1. A per-run JSONL metrics file (one JSON object per line, one per task).
  2. A human-readable Markdown summary report.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from issuebot.benchmark.validator import ValidationResult
from issuebot.models import RunResult, RunStatus

# ─── helpers ──────────────────────────────────────────────────────────────────


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "N/A"
    return f"{100 * numerator / denominator:.1f}%"


def _status_emoji(vr: ValidationResult) -> str:
    if vr.is_genuine_fix:
        return "✅"
    if vr.agent_status == RunStatus.SOLVED:
        return "⚠️"  # solved but validation failed
    return "❌"


# ─── JSONL metrics ────────────────────────────────────────────────────────────


def build_metrics(
    results: list[RunResult],
    validations: list[ValidationResult],
) -> list[dict[str, Any]]:
    """Build one metrics dict per result."""
    val_map = {v.task_id: v for v in validations}
    metrics: list[dict[str, Any]] = []
    for r in results:
        vr = val_map.get(r.task_id)
        row: dict[str, Any] = {
            "task_id": r.task_id,
            "run_id": r.run_id,
            "agent_status": r.status.value,
            "genuine_fix": vr.is_genuine_fix if vr else None,
            "patch_applies": vr.patch_applies if vr else None,
            "full_suite_passed": vr.full_suite_passed if vr else None,
            "hidden_tests_passed": r.hidden_tests_passed,
            "steps": len(r.steps),
            "input_tokens": r.total_input_tokens,
            "output_tokens": r.total_output_tokens,
            "cost_usd": round(r.total_cost_usd, 6),
            "wall_seconds": round(r.wall_seconds, 2),
            "model": r.model_config_name,
            "explanation": r.explanation,
        }
        metrics.append(row)
    return metrics


def write_jsonl(metrics: list[dict[str, Any]], out_path: Path) -> None:
    """Write metrics as JSONL to *out_path*."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in metrics:
            f.write(json.dumps(row) + "\n")


# ─── Markdown report ──────────────────────────────────────────────────────────


def build_report(
    results: list[RunResult],
    validations: list[ValidationResult],
    *,
    model: str = "unknown",
    timestamp: str | None = None,
) -> str:
    """Return a Markdown benchmark report string."""
    ts = timestamp or datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    val_map = {v.task_id: v for v in validations}

    n_total = len(results)
    n_solved = sum(1 for r in results if r.status == RunStatus.SOLVED)
    n_genuine = sum(1 for v in validations if v.is_genuine_fix)
    total_cost = sum(r.total_cost_usd for r in results)
    avg_steps = (sum(len(r.steps) for r in results) / n_total) if n_total else 0
    avg_wall = (sum(r.wall_seconds for r in results) / n_total) if n_total else 0

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

    lines: list[str] = [
        "# IssueBot Benchmark Report",
        "",
        f"**Model:** `{model}`  ",
        f"**Date:** {ts}  ",
        f"**Tasks:** {n_total}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Solved (agent) | {n_solved}/{n_total} ({_pct(n_solved, n_total)}) |",
        f"| Genuine fixes (patch + full suite) | {n_genuine}/{n_total} ({_pct(n_genuine, n_total)}) |",
        f"| Total cost | ${total_cost:.4f} |",
        f"| Avg steps | {avg_steps:.1f} |",
        f"| Avg wall time | {avg_wall:.1f}s |",
        "",
        "### Status breakdown",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines += [
        "",
        "## Per-task results",
        "",
        "| # | Task | Status | Fix? | Steps | Cost | Time | Notes |",
        "|---|------|--------|------|-------|------|------|-------|",
    ]

    for i, r in enumerate(results, 1):
        vr = val_map.get(r.task_id)
        emoji = _status_emoji(vr) if vr else "❓"
        genuine = "Yes" if (vr and vr.is_genuine_fix) else "No"
        notes = ""
        if vr and vr.notes:
            notes = vr.notes[:80].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {i} | `{r.task_id}` | {r.status.value} | {emoji} {genuine} "
            f"| {len(r.steps)} | ${r.total_cost_usd:.4f} | {r.wall_seconds:.1f}s "
            f"| {notes} |"
        )

    lines += [
        "",
        "## Failure analysis",
        "",
    ]

    failures = [r for r in results if r.status != RunStatus.SOLVED]
    if not failures:
        lines.append("🎉 All tasks solved!")
    else:
        for r in failures:
            vr = val_map.get(r.task_id)
            lines += [
                f"### `{r.task_id}` — {r.status.value}",
                "",
                f"- **Explanation:** {r.explanation or '(none)'}",
            ]
            if vr and vr.notes:
                lines.append(f"- **Validation notes:** {vr.notes[:300]}")
            lines.append("")

    return "\n".join(lines) + "\n"


def write_report(report: str, out_path: Path) -> None:
    """Write *report* string to *out_path*."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
