from core.chat_core.providers.anthropic_provider import ANTHROPIC_API_URL, AnthropicProvider


def test_anthropic_requests_go_to_anthropic_even_when_env_points_elsewhere(monkeypatch):
    # A proxy URL or auth token in the environment must not receive the user's key
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "some-other-token")

    provider = AnthropicProvider(api_key="sk-ant-user-key")

    assert str(provider._client.base_url).rstrip("/") == ANTHROPIC_API_URL
    assert provider._client.auth_token is None
    assert provider._client.api_key == "sk-ant-user-key"
