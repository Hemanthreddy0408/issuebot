"""Token pricing and cost calculation.

PRICING is intentionally empty: add entries keyed by exact model name, in USD per
million tokens. UPDATE WITH CURRENT PROVIDER PRICES; nothing here is authoritative.
Models missing from the table use the placeholder fallback from settings.
"""

import logging
from dataclasses import dataclass

from issuebot.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float


PRICING: dict[str, ModelPrice] = {
    "gemini-2.5-flash": ModelPrice(
        input=0.075, output=0.30, cache_read=0.01875, cache_write=0.075
    ),
    "gemini-2.0-flash": ModelPrice(
        input=0.10, output=0.40, cache_read=0.025, cache_write=0.10
    ),
    "gemini-1.5-flash": ModelPrice(
        input=0.075, output=0.30, cache_read=0.01875, cache_write=0.075
    ),
    "gemini-2.5-pro": ModelPrice(
        input=1.25, output=5.00, cache_read=0.3125, cache_write=1.25
    ),
    "gemini-1.5-pro": ModelPrice(
        input=1.25, output=5.00, cache_read=0.3125, cache_write=1.25
    ),
}
_warned: set[str] = set()


def get_price(model: str) -> ModelPrice:
    """Look up a model's price, falling back to placeholder settings."""
    if model in PRICING:
        return PRICING[model]
    if model not in _warned:
        _warned.add(model)
        logger.warning("No price for model %r; using placeholder fallback prices", model)
    s = get_settings()
    return ModelPrice(
        input=s.fallback_input_per_mtok,
        output=s.fallback_output_per_mtok,
        cache_read=s.fallback_input_per_mtok * 0.1,
        cache_write=s.fallback_input_per_mtok * 1.25,
    )


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Return USD cost. `input_tokens` excludes cache read/write tokens."""
    p = get_price(model)
    return (
        input_tokens * p.input
        + output_tokens * p.output
        + cache_read_tokens * p.cache_read
        + cache_write_tokens * p.cache_write
    ) / 1_000_000
