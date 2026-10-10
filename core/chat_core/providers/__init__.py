from ..settings import Settings
from .anthropic_provider import AnthropicProvider
from .base import (
    Citation,
    ModelProvider,
    ProviderError,
    ProviderEvent,
    ProviderStreamError,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
)
from .openrouter_provider import OpenRouterProvider

PROVIDERS: dict[str, type[ModelProvider]] = {
    "anthropic": AnthropicProvider,
    "openrouter": OpenRouterProvider,
}


def create_provider(settings: Settings) -> ModelProvider:
    provider_class = PROVIDERS.get(settings.provider)

    if provider_class is None:
        raise RuntimeError(f"Unknown AI_PROVIDER: {settings.provider}")

    return provider_class(api_key=settings.api_key, max_tokens=settings.max_tokens)


__all__ = [
    "PROVIDERS",
    "AnthropicProvider",
    "Citation",
    "ModelProvider",
    "OpenRouterProvider",
    "ProviderError",
    "ProviderEvent",
    "ProviderStreamError",
    "ReplyTruncated",
    "TextDelta",
    "TruncatedReplyError",
    "create_provider",
]
