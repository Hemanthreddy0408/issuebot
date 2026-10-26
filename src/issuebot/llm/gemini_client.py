"""Google Gemini API client using the official `google-genai` SDK."""

import logging
import time
import uuid
from typing import Any

from issuebot.llm.base import LLMResponse
from issuebot.models import ToolCall

logger = logging.getLogger(__name__)


class GeminiClient:
    """LLMClient backed by the official `google-genai` SDK."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str = "",
        max_tokens: int = 4096,
        client: Any = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key or None)
        self._client = client

    def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """Call the Gemini API and normalize the response."""
        from google.genai import types

        call_id_to_name: dict[str, str] = {}
        contents: list[types.Content] = []

        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            raw_content = msg.get("content")
            parts: list[types.Part] = []

            if isinstance(raw_content, str):
                if raw_content:
                    parts.append(types.Part.from_text(text=raw_content))
            elif isinstance(raw_content, list):
                for block in raw_content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        tval = block.get("text", "")
                        if tval:
                            parts.append(types.Part.from_text(text=tval))
                    elif btype == "tool_use":
                        cid = str(block.get("id", ""))
                        cname = str(block.get("name", ""))
                        cargs = dict(block.get("input") or {})
                        if cid and cname:
                            call_id_to_name[cid] = cname
                        parts.append(types.Part.from_function_call(name=cname, args=cargs))
                    elif btype == "tool_result":
                        cid = str(block.get("tool_use_id", ""))
                        fname = call_id_to_name.get(cid, "unknown_tool")
                        out_val = str(block.get("content", ""))
                        is_err = bool(block.get("is_error", False))
                        parts.append(
                            types.Part.from_function_response(
                                name=fname,
                                response={"output": out_val, "is_error": is_err},
                            )
                        )

            if parts:
                contents.append(types.Content(role=role, parts=parts))

        fn_decls: list[dict[str, Any]] = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            }
            for t in tools
        ]

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": self.max_tokens,
        }
        if system:
            config_kwargs["system_instruction"] = system
        if fn_decls:
            config_kwargs["tools"] = [{"function_declarations": fn_decls}]

        config = types.GenerateContentConfig(**config_kwargs)

        start = time.monotonic()
        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        texts: list[str] = []
        calls: list[ToolCall] = []

        if resp.candidates:
            for candidate in resp.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        text = getattr(part, "text", None)
                        if text:
                            texts.append(text)
                        fc = getattr(part, "function_call", None)
                        if fc:
                            cid = getattr(fc, "id", None) or f"call_{uuid.uuid4().hex[:8]}"
                            calls.append(
                                ToolCall(
                                    id=cid,
                                    name=fc.name,
                                    arguments=dict(fc.args or {}),
                                )
                            )

        usage = getattr(resp, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        cache_read_tokens = getattr(usage, "cached_content_token_count", 0) or 0

        return LLMResponse(
            text="\n".join(texts).strip() or None,
            tool_calls=calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=0,
            model=self.model,
            latency_ms=latency_ms,
        )
