"""AI provider selection."""

from __future__ import annotations

from functools import lru_cache

from app.ai.base import AIProvider, AIProviderError
from app.ai.offline_provider import OfflineProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings


@lru_cache
def get_ai_provider() -> AIProvider:
    """Return the configured provider. Uses the offline provider by default."""
    settings = get_settings()
    if settings.ai_provider == "openai":
        return OpenAIProvider(settings)
    return OfflineProvider()


def reset_provider_cache() -> None:
    get_ai_provider.cache_clear()


__all__ = ["AIProvider", "AIProviderError", "OfflineProvider", "OpenAIProvider", "get_ai_provider", "reset_provider_cache"]
