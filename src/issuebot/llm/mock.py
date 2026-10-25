"""Scripted LLM for offline tests (no network, no cost)."""

import itertools
from typing import Any

from issuebot.llm.base import LLMResponse
from issuebot.models import ToolCall

_ids = itertools.count(1)


def make_response(
    text: str | None = None, *calls: tuple[str, dict[str, Any]], tokens: tuple[int, int] = (100, 20)
) -> LLMResponse:
    """Build an LLMResponse from (tool_name, arguments) tuples."""
    tool_calls = [
        ToolCall(id=f"call_{next(_ids)}", name=name, arguments=args) for name, args in calls
    ]
    return LLMResponse(
        text=text,
        tool_calls=tool_calls,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        model="mock-model",
    )


class ScriptedLLM:
    """Returns pre-scripted responses in order; fails loudly if the script runs out."""

    model = "mock-model"

    def __init__(self, turns: list[LLMResponse]) -> None:
        self.turns = list(turns)
        self.calls: list[list[dict[str, Any]]] = []

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """Pop the next scripted turn."""
        self.calls.append(list(messages))
        if not self.turns:
            raise AssertionError("ScriptedLLM ran out of scripted turns")
        return self.turns.pop(0)
