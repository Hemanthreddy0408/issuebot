"""Application settings loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    strong_model: str = "claude-sonnet-5-5"
    cheap_model: str = "claude-haiku-5-5"
    max_steps: int = 25
    max_cost_usd: float = 0.50
    max_wall_seconds: int = 600
    test_timeout_seconds: int = 60
    runs_dir: str = "runs"
    # Docker Sandbox settings (Section 9.1)
    sandbox_image: str = "issuebot-sandbox:latest"
    sandbox_mem_mb: int = 512
    sandbox_cpus: float = 1.0
    sandbox_timeout_seconds: int = 60
    use_docker_sandbox: bool = True
    # Placeholder prices, update with current provider prices.
    fallback_input_per_mtok: float = 3.0
    fallback_output_per_mtok: float = 15.0


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
