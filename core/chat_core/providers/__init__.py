from ..settings import DEFAULT_MAX_TOKENS, Settings
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
    Usage,
)
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider

PROVIDERS: dict[str, type[ModelProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
}


def create_provider(settings: Settings) -> ModelProvider:
    provider_class = PROVIDERS.get(settings.provider)

    if provider_class is None:
        raise RuntimeError(f"Unknown AI_PROVIDER: {settings.provider}")

    return provider_class(api_key=settings.api_key, max_tokens=settings.max_tokens)


def create_provider_for(
    provider_name: str,
    api_key: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> ModelProvider:
    # Used for keys that belong to one user, so the key is passed in rather than read from env
    provider_class = PROVIDERS.get(provider_name)

    if provider_class is None:
        raise RuntimeError(f"Unknown provider: {provider_name}")

    return provider_class(api_key=api_key, max_tokens=max_tokens)


__all__ = [
    "PROVIDERS",
    "AnthropicProvider",
    "Citation",
    "ModelInfo",
    "ModelProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "ProviderError",
    "ProviderEvent",
    "ProviderStreamError",
    "ReplyReset",
    "ReplyTruncated",
    "TextDelta",
    "TruncatedReplyError",
    "Usage",
    "create_provider",
    "create_provider_for",
]
