import json
from types import SimpleNamespace

from backend.app import create_app
from core.chat_core.key_vault import KeyVault
from core.chat_core.providers import AnthropicProvider, ModelInfo, OpenRouterProvider, ProviderError
from core.chat_core.store import InMemorySessionStore
from tests.support import USER_ID, sign_in


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
        SimpleNamespace(id="anthropic/claude-haiku-4.5:batch", name="Anthropic: Claude Haiku 4.5 (batch)"),
    ]
    provider = OpenRouterProvider(api_key="test-key")
    calls = []

    def list_for_user(*, security):
        calls.append(security)
        return SimpleNamespace(result=SimpleNamespace(data=sdk_models))

    provider._client = SimpleNamespace(models=SimpleNamespace(list_for_user=list_for_user))

    assert provider.list_models() == [
        ModelInfo(id="anthropic/claude-haiku-4.5", name="Anthropic: Claude Haiku 4.5"),
    ]
    assert calls == [{"bearer": "test-key"}]


class FailingProvider:
    def list_models(self):
        raise ProviderError("upstream down")


class RecordingProvider:
    def __init__(self, models: list[ModelInfo]) -> None:
        self.models = models

    def list_models(self):
        return self.models


def save_key(store, provider: str, api_key: str, user_id: str = USER_ID) -> None:
    sealed = KeyVault.from_env().encrypt(user_id, provider, api_key)
    store.save_api_key(user_id, provider, sealed, api_key[-4:])


def patch_provider_factory(monkeypatch, make_provider):
    # Provider construction is the only thing replaced; the key is still read from the store
    calls: list[tuple[str, str]] = []

    def fake_create(provider_name: str, api_key: str, max_tokens: int = 0):
        calls.append((provider_name, api_key))
        return make_provider(provider_name)

    monkeypatch.setattr("core.chat_core.provider_pool.create_provider_for", fake_create)
    return calls


def test_models_endpoint_lists_requested_provider(monkeypatch):
    store = InMemorySessionStore()
    save_key(store, "openrouter", "sk-or-user-key")
    calls = patch_provider_factory(monkeypatch, lambda name: RecordingProvider([ModelInfo(id="m1", name="Model One")]))
    client = sign_in(create_app(store=store).test_client())

    response = client.get("/api/models?provider=OpenRouter")

    assert response.status_code == 200
    assert response.get_json() == {
        "provider": "openrouter",
        "models": [{"id": "m1", "name": "Model One"}],
    }
    assert calls == [("openrouter", "sk-or-user-key")]


def test_models_endpoint_defaults_to_configured_provider(monkeypatch):
    store = InMemorySessionStore()
    save_key(store, "anthropic", "sk-ant-user-key")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    calls = patch_provider_factory(monkeypatch, lambda name: RecordingProvider([]))
    client = sign_in(create_app(store=store).test_client())

    response = client.get("/api/models")

    assert response.get_json()["provider"] == "anthropic"
    assert calls == [("anthropic", "sk-ant-user-key")]


def test_models_endpoint_rejects_unknown_provider():
    client = sign_in(create_app(store=InMemorySessionStore()).test_client())

    response = client.get("/api/models?provider=nope")

    assert response.status_code == 400
    assert "Unknown provider: nope" in response.get_json()["error"]


def test_models_endpoint_asks_for_a_key_when_the_user_has_none(monkeypatch):
    store = InMemorySessionStore()
    save_key(store, "openrouter", "sk-or-someone-elses-key", user_id="other-user")
    patch_provider_factory(monkeypatch, lambda name: RecordingProvider([]))
    client = sign_in(create_app(store=store).test_client())

    response = client.get("/api/models?provider=openrouter")

    assert response.status_code == 409
    assert response.get_json()["code"] == "api_key_required"


def test_models_endpoint_maps_upstream_failure_to_bad_gateway(monkeypatch):
    store = InMemorySessionStore()
    save_key(store, "anthropic", "sk-ant-user-key")
    patch_provider_factory(monkeypatch, lambda name: FailingProvider())
    client = sign_in(create_app(store=store).test_client())

    response = client.get("/api/models?provider=anthropic")

    assert response.status_code == 502
    assert json.loads(response.get_data(as_text=True)) == {"error": "upstream down"}
