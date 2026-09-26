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