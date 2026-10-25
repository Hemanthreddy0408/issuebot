"""Context helpers: output truncation and the initial repo overview."""

from issuebot.repo.workspace import Workspace

MAX_OUTPUT_CHARS = 4000


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    """Cap text at `limit` chars with an explicit marker. Returns (text, was_truncated)."""
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n[truncated {len(text) - limit} characters]", True


def build_overview(ws: Workspace, max_files: int = 150) -> str:
    """Compact repo overview: file listing plus test files."""
    tests = ws.test_files()
    return (
        f"Repository files:\n{ws.tree(max_files)}\n\n"
        f"Test files:\n{chr(10).join(tests) if tests else '(none found)'}"
    )
