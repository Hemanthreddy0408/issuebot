"""Detects an agent stuck repeating itself."""

import json
from typing import Any


class LoopDetector:
    """Flags (a) the same call with identical args N times in a row, or
    (b) the same test output M times with no file edits in between."""

    def __init__(self, repeat_limit: int = 3, same_failure_limit: int = 4) -> None:
        self.repeat_limit = repeat_limit
        self.same_failure_limit = same_failure_limit
        self._last_key: str | None = None
        self._streak = 0
        self._fail_key: tuple[str, int] | None = None
        self._fail_count = 0

    def record_call(self, name: str, arguments: dict[str, Any]) -> bool:
        """Record a tool call. Returns True if a loop is detected."""
        key = name + json.dumps(arguments, sort_keys=True, default=str)
        self._streak = self._streak + 1 if key == self._last_key else 1
        self._last_key = key
        return self._streak >= self.repeat_limit

    def record_test_failure(self, output_digest: str, edit_count: int) -> bool:
        """Record a failing test output. Returns True if a loop is detected."""
        key = (output_digest, edit_count)
        self._fail_count = self._fail_count + 1 if key == self._fail_key else 1
        self._fail_key = key
        return self._fail_count >= self.same_failure_limit
