# Progress

## Phase 1: Skeleton and core loop: DONE
- Scaffold, config, models, LLM interface + Anthropic client (prompt-cache marker, cache token accounting)
- Tools: search_code (regex + ast symbols), read_file, edit_file, git_diff, finish
- Agent loop with budgets, loop detector, enforced explore-before-edit, enforced final verification
- JSONL tracing, cost calculation, Typer CLI (`issuebot solve`)
- Offline unit tests with scripted mock LLM; ruff + mypy clean

## Phase 2: Docker sandbox and security layer: DONE (awaiting approval)
- Docker sandbox runner (`src/issuebot/sandbox/docker_runner.py`), `sandbox/Dockerfile.sandbox`, and in-container `sandbox/runner.py`
- Built `issuebot-sandbox:latest` container with non-root user (10001:10001), read-only root, tmpfs `/tmp`, and `network_mode="none"`
- Command policy (`src/issuebot/security/command_policy.py`) with pytest allowlist, metacharacter denial, and flag restrictions
- Path guard (`src/issuebot/security/path_guard.py`) enforcing workspace boundaries, blocking `.git/` & `hidden_tests/`, and preventing assertion deletion or weakening
- Prompt injection defense (`src/issuebot/security/injection.py`) with `<untrusted_...>` boundary tagging and pattern detection
- Secret redaction (`src/issuebot/security/secrets.py`) scrubbing API keys, tokens, and sensitive data from tool outputs, traces, and patches
- 83 tests passing (35 unit tests + 48 security tests in `tests/security/`), including live Docker container no-network test and injection-obedience test
- `ruff check .` clean; `mypy src tests` clean (39 source files)

## Next: Phase 3: Benchmark (seed repos, task generator, validation script, runner, metrics, failure analysis)
