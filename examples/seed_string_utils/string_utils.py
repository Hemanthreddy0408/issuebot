"""String utility helpers."""


def truncate(text: str, max_len: int, suffix: str = "...") -> str:
    """Return *text* truncated to *max_len* characters (inclusive of *suffix*).

    If *text* fits in *max_len*, return it unchanged.
    """
    if len(text) <= max_len:
        return text
    # BUG: should be max_len - len(suffix), not max_len - len(suffix) - 1
    cut = max_len - len(suffix) - 1
    return text[:cut] + suffix


def word_count(text: str) -> int:
    """Count whitespace-delimited words in *text*."""
    return len(text.split())


def is_palindrome(text: str) -> bool:
    """Return True if *text* (lowercased, letters only) is a palindrome."""
    cleaned = "".join(c.lower() for c in text if c.isalpha())
    return cleaned == cleaned[::-1]
