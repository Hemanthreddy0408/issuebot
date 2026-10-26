`truncate("Hello, World!", 10)` should return `"Hello, ..."` (7 chars + "..." = 10 total),
but it returns `"Hello,..."` (6 chars + "..." = 9 total) — one character too short.

The function is cutting one character too many when it computes the slice index.
Expected: `text[:max_len - len(suffix)]` — not `text[:max_len - len(suffix) - 1]`.
