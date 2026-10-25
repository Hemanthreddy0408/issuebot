"""Prompt injection defense: untrusted content wrapping and pattern detection."""

import re
from dataclasses import dataclass

SUSPICIOUS_INJECTION_PATTERNS = [
    (re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE), "ignore_instructions"),
    (re.compile(r"disregard\s+(?:all\s+)?(?:prior|previous)\s+instructions", re.IGNORECASE), "disregard_instructions"),
    (re.compile(r"(?:print|dump|show|reveal|echo)\s+(?:all\s+)?(?:the\s+)?(?:system\s+prompt|instructions)", re.IGNORECASE), "leak_system_prompt"),
    (re.compile(r"(?:print|dump|show|reveal|echo|send|exfiltrate)\s+(?:all\s+)?(?:the\s+)?(?:environment\s+variables|env\s+vars|\$ENV)", re.IGNORECASE), "leak_env_vars"),
    (re.compile(r"(?:https?://|ftp://)[^\s<>\"']+", re.IGNORECASE), "external_url"),
    (re.compile(r"\b(?:curl|wget|nc|netcat)\s+[^\s]+", re.IGNORECASE), "network_command"),
    (re.compile(r"(?:new\s+instructions|system\s+override|admin\s+override):", re.IGNORECASE), "instruction_override"),
    (re.compile(r"[A-Za-z0-9+/=]{60,}", re.IGNORECASE), "potential_base64_payload"),
]


@dataclass(frozen=True)
class InjectionDetection:
    """Outcome of scanning text for prompt injection patterns."""

    flagged: bool
    patterns: list[str]
    details: str | None = None


def wrap_untrusted(tag: str, content: str) -> str:
    """Wrap untrusted data in XML-style boundary markers.

    Instructs the LLM that content within these boundaries represents passive data,
    not actionable instructions.
    """
    clean_tag = tag.strip().lower()
    return f"<{clean_tag}>\n{content}\n</{clean_tag}>"


def detect_injection(text: str) -> InjectionDetection:
    """Scan `text` for common prompt injection and exfiltration patterns."""
    if not text:
        return InjectionDetection(flagged=False, patterns=[])

    found_patterns: list[str] = []
    matched_snippets: list[str] = []

    for pattern, name in SUSPICIOUS_INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            found_patterns.append(name)
            matched_snippets.append(f"{name}: '{match.group(0)[:60]}'")

    if found_patterns:
        return InjectionDetection(
            flagged=True,
            patterns=found_patterns,
            details="; ".join(matched_snippets),
        )

    return InjectionDetection(flagged=False, patterns=[])
