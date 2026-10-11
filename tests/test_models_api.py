import json
from types import SimpleNamespace

from backend.app import create_app
from core.chat_core.providers import AnthropicProvider, ModelInfo, OpenRouterProvider, ProviderError
from core.chat_core.store import InMemorySessionStore


class FakeModels:
    def __init__(self, models: list) -> None:
        self.models = models

    def list(self):
        return self.models


def test_anthropic_list_models_returns_id_and_display_name():
    models = [SimpleNamespace(id="claude-haiku-5-5", display_name="Claude Haiku 5.5")]
    client = SimpleNamespace(models=FakeModels(models))
    provider = AnthropicProvider(api_key="test-key", client=client)

    assert provider.list_models() == [ModelInfo(id="claude-haiku-5-5", name="Claude Haiku 5.5")]


def test_openrouter_list_models_maps_sdk_models_to_id_and_name():
    sdk_models = [
        SimpleNamespace(id="anthropic/claude-haiku-4.5", name="Anthropic: Claude Haiku 4.5"),
    ]
    provider = OpenRouterProvider(api_key="test-key")
    provider._client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: SimpleNamespace(result=SimpleNamespace(data=sdk_models)),
        ),
    )

    assert provider.list_models() == [
        ModelInfo(id="anthropic/claude-haiku-4.5", name="Anthropic: Claude Haiku 4.5"),
    ]


class FailingProvider:
    def list_models(self):
        raise ProviderError("upstream down")


class RecordingProvider:
    def __init__(self, models: list[ModelInfo]) -> None:
        self.models = models

    def list_models(self):
        return self.models


def test_models_endpoint_lists_requested_provider(monkeypatch):
    calls: list[str] = []

    def fake_create(provider_name: str):
        calls.append(provider_name)
        return RecordingProvider([ModelInfo(id="m1", name="Model One")])

    monkeypatch.setattr("backend.app.create_provider_by_name", fake_create)
    client = create_app(store=InMemorySessionStore()).test_client()

    response = client.get("/api/models?provider=OpenRouter")

    assert response.status_code == 200
    assert response.get_json() == {
        "provider": "openrouter",
        "models": [{"id": "m1", "name": "Model One"}],
    }
    assert calls == ["openrouter"]


def test_models_endpoint_defaults_to_configured_provider(monkeypatch):
    calls: list[str] = []
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setattr(
        "backend.app.create_provider_by_name",
        lambda name: calls.append(name) or RecordingProvider([]),
    )
    client = create_app(store=InMemorySessionStore()).test_client()

    response = client.get("/api/models")

    assert response.get_json()["provider"] == "anthropic"
    assert calls == ["anthropic"]


def test_models_endpoint_rejects_unknown_provider():
    client = create_app(store=InMemorySessionStore()).test_client()

    response = client.get("/api/models?provider=nope")

    assert response.status_code == 400
    assert "Unknown provider: nope" in response.get_json()["error"]


def test_models_endpoint_reports_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = create_app(store=InMemorySessionStore()).test_client()

    response = client.get("/api/models?provider=openrouter")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "OPENROUTER_API_KEY is required for the openrouter provider",
    }


def test_models_endpoint_maps_upstream_failure_to_bad_gateway(monkeypatch):
    monkeypatch.setattr("backend.app.create_provider_by_name", lambda name: FailingProvider())
    client = create_app(store=InMemorySessionStore()).test_client()

    response = client.get("/api/models?provider=anthropic")

    assert response.status_code == 502
    assert json.loads(response.get_data(as_text=True)) == {"error": "upstream down"}
