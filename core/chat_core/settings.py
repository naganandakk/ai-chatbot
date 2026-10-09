import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str
    model: str
    database_path: str = "data/chat.duckdb"

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("AI_PROVIDER", "").lower()

        if provider not in {"anthropic", "openrouter"}:
            raise RuntimeError(
                "AI_PROVIDER must be set to 'anthropic' or 'openrouter'"
            )

        key_name = (
            "OPENROUTER_API_KEY"
            if provider == "openrouter"
            else "ANTHROPIC_API_KEY"
        )
        api_key = os.getenv(key_name)

        if not api_key:
            raise RuntimeError(f"{key_name} is required when AI_PROVIDER={provider}")

        default_model = (
            "anthropic/claude-haiku-4.5"
            if provider == "openrouter"
            else "claude-haiku-4-5"
        )
        model = os.getenv("CLAUDE_MODEL", default_model)
        database_path = os.getenv("CHAT_DATABASE_PATH", "data/chat.duckdb")

        return cls(
            provider=provider,
            api_key=api_key,
            model=model,
            database_path=database_path,
        )