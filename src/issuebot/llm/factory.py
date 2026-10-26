"""Factory for instantiating LLM clients."""

from issuebot.config import Settings, get_settings
from issuebot.llm.anthropic_client import AnthropicClient
from issuebot.llm.base import LLMClient
from issuebot.llm.gemini_client import GeminiClient


def create_llm_client(
    model: str | None = None,
    settings: Settings | None = None,
) -> LLMClient:
    """Create an LLMClient instance based on model name and configuration.

    If model starts with 'gemini' or 'gemini/', creates a GeminiClient.
    If model is unspecified:
      - If gemini_api_key is provided and anthropic_api_key is not, defaults to gemini_model.
      - Otherwise defaults to strong_model (Anthropic).
    """
    settings = settings or get_settings()

    target_model = model
    if not target_model:
        if settings.gemini_api_key and not settings.anthropic_api_key:
            target_model = settings.gemini_model
        else:
            target_model = settings.strong_model

    clean_model = target_model.removeprefix("gemini/")
    if target_model.startswith("gemini"):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set (see .env.example).")
        return GeminiClient(clean_model, api_key=settings.gemini_api_key)

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set (see .env.example).")
    return AnthropicClient(target_model, api_key=settings.anthropic_api_key)
