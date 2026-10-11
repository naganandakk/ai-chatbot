from ..settings import DEFAULT_MAX_TOKENS, Settings, api_key_from_env
from .anthropic_provider import AnthropicProvider
from .base import (
    Citation,
    ModelInfo,
    ModelProvider,
    ProviderError,
    ProviderEvent,
    ProviderStreamError,
    ReplyReset,
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


def create_provider_by_name(provider_name: str) -> ModelProvider:
    # Used when listing models for a provider that may not be the configured AI_PROVIDER
    provider_class = PROVIDERS.get(provider_name)

    if provider_class is None:
        raise RuntimeError(f"Unknown provider: {provider_name}")

    return provider_class(api_key=api_key_from_env(provider_name), max_tokens=DEFAULT_MAX_TOKENS)


__all__ = [
    "PROVIDERS",
    "AnthropicProvider",
    "Citation",
    "ModelInfo",
    "ModelProvider",
    "OpenRouterProvider",
    "ProviderError",
    "ProviderEvent",
    "ProviderStreamError",
    "ReplyReset",
    "ReplyTruncated",
    "TextDelta",
    "TruncatedReplyError",
    "create_provider",
    "create_provider_by_name",
]
