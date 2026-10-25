"""Step / cost / wall-time budgets."""

import time
from dataclasses import dataclass, field


class BudgetExceeded(Exception):
    """Raised when any budget limit is hit."""


@dataclass
class Budget:
    """Tracks LLM turns, tokens, cost and wall time."""

    max_steps: int
    max_cost_usd: float
    max_wall_seconds: float
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    start: float = field(default_factory=time.monotonic)

    def record(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        """Account for one LLM turn."""
        self.steps += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd

    @property
    def wall_seconds(self) -> float:
        """Seconds since the budget started."""
        return time.monotonic() - self.start

    def check(self) -> None:
        """Raise BudgetExceeded if any limit has been reached."""
        if self.steps >= self.max_steps:
            raise BudgetExceeded(f"Step budget exhausted ({self.max_steps} steps)")
        if self.cost_usd >= self.max_cost_usd:
            raise BudgetExceeded(f"Cost budget exhausted (${self.cost_usd:.4f})")
        if self.wall_seconds >= self.max_wall_seconds:
            raise BudgetExceeded(f"Wall-time budget exhausted ({self.max_wall_seconds}s)")
