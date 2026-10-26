from string_utils import truncate, word_count, is_palindrome


# --- truncate ---

def test_truncate_short_text_unchanged():
    assert truncate("Hi", 10) == "Hi"


def test_truncate_exact_max_unchanged():
    assert truncate("Hello", 5) == "Hello"


def test_truncate_produces_exactly_max_len():
    result = truncate("Hello, World!", 10)
    assert len(result) == 10, f"Expected 10 chars, got {len(result)}: {result!r}"


def test_truncate_uses_suffix():
    result = truncate("Hello, World!", 10)
    assert result.endswith("..."), f"Expected suffix '...', got: {result!r}"


def test_truncate_custom_suffix():
    result = truncate("Hello, World!", 8, suffix="…")
    assert len(result) == 8
    assert result.endswith("…")


# --- word_count ---

def test_word_count_empty():
    assert word_count("") == 0


def test_word_count_single():
    assert word_count("hello") == 1


def test_word_count_sentence():
    assert word_count("the quick brown fox") == 4


# --- is_palindrome ---

def test_palindrome_simple():
    assert is_palindrome("racecar")


def test_palindrome_with_spaces():
    assert is_palindrome("A man a plan a canal Panama")


def test_not_palindrome():
    assert not is_palindrome("hello")
