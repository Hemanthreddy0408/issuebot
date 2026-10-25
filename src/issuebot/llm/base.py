"""Provider-neutral LLM interface."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from issuebot.models import ToolCall


@dataclass
class LLMResponse:
    """A single model turn."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    model: str = ""
    latency_ms: int = 0


class LLMClient(Protocol):
    """Anything that can produce a model turn from messages + tool schemas.

    Messages use Anthropic-style blocks (text / tool_use / tool_result).
    """

    model: str

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """Return the model's next turn."""
        ...
