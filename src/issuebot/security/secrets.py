"""Secret redaction for logs, traces, tool outputs, and PR descriptions."""

import re
from collections.abc import Iterable

# Regex patterns for common API keys and tokens
SECRET_PATTERNS = [
    # Anthropic API keys (sk-ant-...)
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    # OpenAI API keys (sk-proj-..., sk-...)
    re.compile(r"sk-(?:proj-)?[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    # GitHub personal access tokens, app tokens, OAuth tokens
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{60,}", re.IGNORECASE),
    # AWS access keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Generic Private Key blocks
    re.compile(
        r"-----BEGIN[ A-Z0-9_-]+PRIVATE KEY-----[\s\S]*?-----END[ A-Z0-9_-]+PRIVATE KEY-----"
    ),
    # Common Bearer token authorization headers
    re.compile(r"(?:Bearer|token)\s+[a-zA-Z0-9\-_.]{24,}", re.IGNORECASE),
]

REDACTION_MARKER = "[REDACTED_SECRET]"


def redact_secrets(text: str, custom_secrets: Iterable[str] | None = None) -> str:
    """Scan `text` and replace detected secrets and tokens with [REDACTED_SECRET].

    Optionally also redacts known secret strings passed via `custom_secrets`.
    """
    if not text:
        return text

    redacted = text

    # Redact any explicitly provided sensitive strings (e.g. from app settings)
    if custom_secrets:
        for secret in custom_secrets:
            if secret and len(secret) >= 6:
                redacted = redacted.replace(secret, REDACTION_MARKER)

    # Redact based on regex patterns
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTION_MARKER, redacted)

    return redacted
