# Decisions

1. **Default model names** are set to `claude-sonnet-5-5` / `claude-haiku-5-5` in `config.py` and `.env.example` so the CLI works out of the box. Update them as provider models change.
2. **`ToolCall.name` is `str`**, not a `Literal`, so a hallucinated tool name is a recoverable tool error rather than a validation crash.
3. **Diffs use `difflib`** against a pristine snapshot instead of `git`, so no git binary is required in the workspace.
4. **Pricing table is empty** (`observability/cost.py`). Unknown models use clearly-labelled placeholder fallback prices from settings. Fill in real prices before trusting cost numbers or cost budgets.
5. **Docker Sandbox Execution (Phase 2):** Tests execute in an isolated Docker container (`issuebot-sandbox:latest`) with `network_mode="none"`, read-only root, 64MB writable tmpfs on `/tmp`, non-root user (10001:10001), 1 CPU, 512MB RAM, `cap_drop=["ALL"]`, and `no-new-privileges`. A local subprocess runner is retained only as a fallback when Docker is explicitly disabled.
6. **Plan-before-edit** is enforced as "explore (search/read) before editing", per spec 7.1.
7. **Mandatory final verification:** `finish` triggers a loop-run test pass. Two failed finishes end the run as `failed_tests`.
8. **Test Weakening Detection via AST:** `PathGuard` parses Python AST to block deletions of test functions or reductions in `assert` statement count, preventing test tampering while allowing agent-written test additions.
9. **Prompt Injection Defense-in-Depth:** Injected issue text is wrapped in `<untrusted_issue>` tags and scanned for adversarial patterns (recorded in trace events); security boundaries are strictly enforced by the tool layer and sandbox, ensuring that even if an LLM obeys an injection, exfiltration and damage are impossible.
10. **Universal Secret Redaction:** Scrubbing patterns for Anthropic, OpenAI, GitHub, AWS, and private keys are applied automatically to all tool outputs, traces, and run result summaries.
