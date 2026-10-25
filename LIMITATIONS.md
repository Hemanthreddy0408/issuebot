# IssueBot Limitations

> This document tracks the known constraints and failure modes of IssueBot.
> Detailed trace examples and empirical failure rates will be populated from benchmark runs (Phase 3 & 4).

## Architectural Limitations

1. **Python Only**: IssueBot currently inspects, indexes, and tests Python repositories (`pytest`). Multi-language repos or other test runners are out of scope.
2. **Repository Size**: IssueBot is designed for small to medium repositories (3–30 files). Large monorepos with hundreds of modules exceed context limits.
3. **Bug-Fixing Only**: The agent loop is constrained to localized bug fixes where existing or new tests can verify the solution. Open-ended feature development or large architectural refactors are not supported.
4. **Non-Determinism**: LLM reasoning can vary across runs. Benchmarks report averaged pass rates (e.g., `pass@1`) to account for variance.
5. **Sandbox Isolation (Phase 1 Subprocess -> Phase 2 Docker)**:
   - In Phase 1, `run_tests` executes in a local subprocess with a restricted command allowlist for initial development.
   - True isolation (no-network, CPU/memory limits, non-root user) is provided in Phase 2 via the Docker sandbox container.
