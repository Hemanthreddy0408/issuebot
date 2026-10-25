"""Always-on structured JSONL tracing."""

import json
import time
from pathlib import Path
from typing import Any


class Tracer:
    """Appends one JSON record per event. With path=None it is a no-op."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, **record: Any) -> None:
        """Write a record with a timestamp."""
        if self.path is None:
            return
        record["ts"] = time.time()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
