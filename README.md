# IssueBot (Phase 1)

Autonomous bug-fixing agent: reads an issue, explores a Python repo with constrained tools,
edits, runs tests, iterates, and outputs a patch.

> Phase 1 status: core loop and CLI. `run_tests` is a local subprocess (temporary).
> Docker sandbox, benchmark, GitHub PRs, dashboard and CI come in later phases.
> **Results: Not yet run.**

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # set ANTHROPIC_API_KEY, check model names
pytest                      # offline, uses a mock LLM
issuebot solve --repo examples/seed_cart --issue-file examples/seed_cart/ISSUE.md
```
The original repo is never modified; the fix is printed as a unified diff (use `--out fix.patch`).
Traces are written to `runs/<run_id>/trace.jsonl`.
# issuebot
