import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

DEFAULT_MAX_TOKENS = 8192

API_KEY_NAMES = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def api_key_from_env(provider: str) -> str:
    key_name = API_KEY_NAMES[provider]
    api_key = os.getenv(key_name)

    if not api_key:
        raise RuntimeError(f"{key_name} is required for the {provider} provider")

    return api_key


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str
    model: str
    database_path: str = "data/chat.duckdb"
    max_tokens: int = DEFAULT_MAX_TOKENS

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("AI_PROVIDER", "").lower()

        if provider not in API_KEY_NAMES:
            raise RuntimeError(
                "AI_PROVIDER must be set to 'anthropic' or 'openrouter'"
            )

        api_key = api_key_from_env(provider)

        default_model = (
            "anthropic/claude-haiku-4.5"
            if provider == "openrouter"
            else "claude-haiku-4-5"
        )
        model = os.getenv("CLAUDE_MODEL", default_model)
        database_path = os.getenv("CHAT_DATABASE_PATH", "data/chat.duckdb")
        max_tokens = _max_tokens_from_env()

        return cls(
            provider=provider,
            api_key=api_key,
            model=model,
            database_path=database_path,
            max_tokens=max_tokens,
        )


def _max_tokens_from_env() -> int:
    raw = os.getenv("MAX_TOKENS", "").strip()

    if not raw:
        return DEFAULT_MAX_TOKENS

    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"MAX_TOKENS must be a whole number, got {raw!r}") from None

    if value <= 0:
        raise RuntimeError(f"MAX_TOKENS must be greater than zero, got {value}")

    return value