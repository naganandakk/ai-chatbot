import pytest

from core.chat_core.settings import Settings


def test_loads_anthropic_settings(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-test-model")

    settings = Settings.from_env()

    assert settings.provider == "anthropic"
    assert settings.api_key == "anthropic-key"
    assert settings.model == "claude-test-model"


def test_loads_openrouter_settings(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)

    settings = Settings.from_env()

    assert settings.provider == "openrouter"
    assert settings.api_key == "openrouter-key"
    assert settings.model == "anthropic/claude-haiku-4.5"


def test_rejects_missing_provider(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    with pytest.raises(
        RuntimeError,
        match="AI_PROVIDER must be set to 'anthropic' or 'openrouter'",
    ):
        Settings.from_env()

def test_loads_database_path(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("CHAT_DATABASE_PATH", "tmp/test-chat.duckdb")

    settings = Settings.from_env()

    assert settings.database_path == "tmp/test-chat.duckdb"

def test_max_tokens_defaults_when_unset(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.delenv("MAX_TOKENS", raising=False)

    assert Settings.from_env().max_tokens == 8192


def test_max_tokens_is_read_from_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("MAX_TOKENS", "4096")

    assert Settings.from_env().max_tokens == 4096


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_rejects_invalid_max_tokens(monkeypatch, value):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("MAX_TOKENS", value)

    with pytest.raises(RuntimeError, match="MAX_TOKENS"):
        Settings.from_env()
