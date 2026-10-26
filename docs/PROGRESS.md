# Progress

## Phase 1: Skeleton and core loop: DONE
- Scaffold, config, models, LLM interface + Anthropic client (prompt-cache marker, cache token accounting)
- Tools: search_code (regex + ast symbols), read_file, edit_file, git_diff, finish
- Agent loop with budgets, loop detector, enforced explore-before-edit, enforced final verification
- JSONL tracing, cost calculation, Typer CLI (`issuebot solve`)
- Offline unit tests with scripted mock LLM; ruff + mypy clean

## Phase 2: Docker sandbox and security layer: DONE
- Docker sandbox runner (`src/issuebot/sandbox/docker_runner.py`), `sandbox/Dockerfile.sandbox`, and in-container `sandbox/runner.py`
- Built `issuebot-sandbox:latest` container with non-root user (10001:10001), read-only root, tmpfs `/tmp`, and `network_mode="none"`
- Command policy (`src/issuebot/security/command_policy.py`) with pytest allowlist, metacharacter denial, and flag restrictions
- Path guard (`src/issuebot/security/path_guard.py`) enforcing workspace boundaries, blocking `.git/` & `hidden_tests/`, and preventing assertion deletion or weakening
- Prompt injection defense (`src/issuebot/security/injection.py`) with `<untrusted_...>` boundary tagging and pattern detection
- Secret redaction (`src/issuebot/security/secrets.py`) scrubbing API keys, tokens, and sensitive data from tool outputs, traces, and patches
- 83 tests passing (35 unit tests + 48 security tests in `tests/security/`), including live Docker container no-network test and injection-obedience test
- `ruff check .` clean; `mypy src tests` clean (39 source files)

## Phase 3: Benchmark: DONE
- Three additional seed repos: `seed_string_utils` (off-by-one in `truncate()`), `seed_bank_account` (missing overdraft check), `seed_date_parser` (wrong leap-year logic for century years divisible by 400)
- `src/issuebot/benchmark/` package: `loader.py` (discovers ISSUE.md repos), `runner.py` (sequential runs + hidden-test post-validation), `validator.py` (applies patch, re-runs full visible suite), `reporter.py` (JSONL metrics + Markdown report)
- `MockLLMClient` stub in `src/issuebot/llm/mock.py` for `--dry-run` benchmark mode (no API key required)
- CLI: `issuebot benchmark run [--dry-run] [--no-validate]` and `issuebot benchmark report <metrics.jsonl>`
- 22 new benchmark tests in `tests/benchmark/test_benchmark.py` — all 105 tests passing
- `ruff check .` clean; `mypy src tests` clean (46 source files)

## Architecture complete — all three phases done
