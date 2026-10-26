from types import SimpleNamespace as NS
from typing import Any

import pytest

from issuebot.config import Settings
from issuebot.llm.anthropic_client import AnthropicClient
from issuebot.llm.factory import create_llm_client
from issuebot.llm.gemini_client import GeminiClient


class FakeModels:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> NS:
        self.kwargs = kwargs
        return NS(
            candidates=[
                NS(
                    content=NS(
                        parts=[
                            NS(text="I will check the file."),
                            NS(
                                text=None,
                                function_call=NS(
                                    id="call_test1",
                                    name="read_file",
                                    args={"path": "main.py"},
                                ),
                            ),
                        ]
                    )
                )
            ],
            usage_metadata=NS(
                prompt_token_count=42,
                candidates_token_count=18,
                cached_content_token_count=5,
            ),
        )


def test_gemini_client_parses_response() -> None:
    fake_models = FakeModels()
    fake_client = NS(models=fake_models)
    client = GeminiClient(model="gemini-2.5-flash", client=fake_client)

    tools: list[dict[str, Any]] = [
        {
            "name": "read_file",
            "description": "Read file contents",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ]
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "Please read main.py"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_test1",
                    "name": "read_file",
                    "input": {"path": "main.py"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_test1",
                    "content": "def main(): pass",
                    "is_error": False,
                }
            ],
        },
    ]

    response = client.complete("System prompt instructions", messages, tools)

    assert response.text == "I will check the file."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_test1"
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].arguments == {"path": "main.py"}
    assert response.input_tokens == 42
    assert response.output_tokens == 18
    assert response.cache_read_tokens == 5
    assert response.model == "gemini-2.5-flash"


def test_create_llm_client_routing() -> None:
    settings = Settings(
        anthropic_api_key="ant-key",
        gemini_api_key="gem-key",
        strong_model="claude-3-7-sonnet",
        gemini_model="gemini-2.5-flash",
    )

    # Route by model prefix
    gemini = create_llm_client("gemini-2.5-flash", settings)
    assert isinstance(gemini, GeminiClient)
    assert gemini.model == "gemini-2.5-flash"

    gemini_prefixed = create_llm_client("gemini/gemini-2.5-pro", settings)
    assert isinstance(gemini_prefixed, GeminiClient)
    assert gemini_prefixed.model == "gemini-2.5-pro"

    claude = create_llm_client("claude-3-7-sonnet", settings)
    assert isinstance(claude, AnthropicClient)
    assert claude.model == "claude-3-7-sonnet"

    # Default to Gemini if only Gemini key is available
    gemini_only = Settings(anthropic_api_key="", gemini_api_key="gem-key")
    client_default = create_llm_client(None, gemini_only)
    assert isinstance(client_default, GeminiClient)

    # Error when key is missing
    no_keys = Settings(anthropic_api_key="", gemini_api_key="")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        create_llm_client("gemini-2.5-flash", no_keys)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        create_llm_client("claude-3-7-sonnet", no_keys)
