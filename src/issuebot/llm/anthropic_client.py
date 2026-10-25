"""Anthropic Messages API client."""

import logging
import time
from typing import Any

from issuebot.llm.base import LLMResponse
from issuebot.models import ToolCall

logger = logging.getLogger(__name__)


class AnthropicClient:
    """LLMClient backed by the official `anthropic` SDK."""

    def __init__(
        self, model: str, api_key: str = "", max_tokens: int = 4096, client: Any = None
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key or None)
        self._client = client

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """Call the Messages API and normalize the response."""
        start = time.monotonic()
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            # Mark the stable system prompt as cacheable.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=tools,
        )
        texts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                texts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        usage = resp.usage
        return LLMResponse(
            text="\n".join(texts).strip() or None,
            tool_calls=calls,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            model=self.model,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
