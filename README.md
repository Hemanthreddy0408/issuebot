# IssueBot

Autonomous bug-fixing agent: reads an issue, explores a Python repo with constrained tools,
edits, runs tests inside an isolated Docker sandbox, iterates, and outputs a patch.

> **Status:** Phase 1 (Core Loop) & Phase 2 (Docker Sandbox & Security Layer) completed.
> 83 unit and security tests passing.
> **Benchmark Results: Not yet run (Phase 3).**

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # set ANTHROPIC_API_KEY, check model names
pytest                      # 83 unit & security tests, offline with mock LLM
issuebot solve --repo examples/seed_cart --issue-file examples/seed_cart/ISSUE.md
```
The original repo is never modified; the fix is printed as a unified diff (use `--out fix.patch`).
Traces are written to `runs/<run_id>/trace.jsonl`.
