from backend.app import create_app
from core.chat_core.key_vault import KeyVault
from core.chat_core.providers import ModelInfo, ProviderError
from core.chat_core.store import InMemorySessionStore
from tests.support import USER_ID, sign_in

SENTINEL_KEY = "sk-ant-sentinel-do-not-leak-1234"


class AcceptingProvider:
    def list_models(self):
        return [ModelInfo(id="m1", name="Model One")]

    def close(self) -> None:
        pass


class RejectingProvider:
    def list_models(self):
        raise ProviderError("invalid x-api-key")

    def close(self) -> None:
        pass


def patch_validation(monkeypatch, provider):
    monkeypatch.setattr("backend.app.api_keys.create_provider_for", lambda *args, **kwargs: provider)


def make_client(store):
    return sign_in(create_app(store=store).test_client())


def test_saving_a_valid_key_stores_it_encrypted_and_returns_only_the_last_four(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)

    response = client.put("/api/me/api-keys/anthropic", json={"apiKey": SENTINEL_KEY})

    assert response.status_code == 200
    assert response.get_json() == {"provider": "anthropic", "configured": True, "last4": "1234"}
    assert SENTINEL_KEY not in response.get_data(as_text=True)

    stored = store.get_api_key(USER_ID, "anthropic")
    assert SENTINEL_KEY.encode() not in stored.sealed.ciphertext
    assert KeyVault.from_env().decrypt(USER_ID, "anthropic", stored.sealed) == SENTINEL_KEY


def test_listing_shows_status_per_provider_without_the_key(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)
    client.put("/api/me/api-keys/anthropic", json={"apiKey": SENTINEL_KEY})

    response = client.get("/api/me/api-keys")

    body = response.get_data(as_text=True)
    assert SENTINEL_KEY not in body
    assert response.get_json() == [
        {"provider": "anthropic", "configured": True, "last4": "1234"},
        {"provider": "openrouter", "configured": False, "last4": None},
    ]


def test_a_rejected_key_is_not_saved(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, RejectingProvider())
    client = make_client(store)

    response = client.put("/api/me/api-keys/anthropic", json={"apiKey": SENTINEL_KEY})

    assert response.status_code == 422
    assert response.get_json()["code"] == "api_key_invalid"
    assert store.get_api_key(USER_ID, "anthropic") is None
    assert SENTINEL_KEY not in response.get_data(as_text=True)


def test_empty_key_and_unknown_provider_are_refused(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)

    empty = client.put("/api/me/api-keys/anthropic", json={"apiKey": "  "})
    unknown = client.put("/api/me/api-keys/nope", json={"apiKey": SENTINEL_KEY})

    assert empty.status_code == 400
    assert empty.get_json()["code"] == "api_key_missing"
    assert unknown.status_code == 404


def test_deleting_a_key_removes_it(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)
    client.put("/api/me/api-keys/anthropic", json={"apiKey": SENTINEL_KEY})

    response = client.delete("/api/me/api-keys/anthropic")

    assert response.get_json() == {"provider": "anthropic", "configured": False, "last4": None}
    assert store.get_api_key(USER_ID, "anthropic") is None


def test_one_users_key_is_not_visible_to_another(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    make_client(store).put("/api/me/api-keys/anthropic", json={"apiKey": SENTINEL_KEY})
    other_client = sign_in(create_app(store=store).test_client(), user_id="user-2")

    listed = other_client.get("/api/me/api-keys").get_json()

    assert listed[0] == {"provider": "anthropic", "configured": False, "last4": None}


def test_sending_without_a_saved_key_streams_an_error_and_saves_nothing(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    store = InMemorySessionStore()
    client = make_client(store)
    session = client.post("/api/sessions").get_json()

    response = client.post(f"/api/sessions/{session['id']}/messages", json={"message": "Hi"})

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "event: error" in body
    assert '"code": "api_key_required"' in body
    assert store.get(USER_ID, session["id"]).messages == []


def test_first_saved_key_becomes_the_provider_in_use(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)

    client.put("/api/me/api-keys/openrouter", json={"apiKey": SENTINEL_KEY})
    client.put("/api/me/api-keys/anthropic", json={"apiKey": "sk-ant-second-key-5678"})

    assert client.get("/api/me/settings").get_json()["activeProvider"] == "openrouter"


def test_choosing_a_provider_requires_its_key(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)

    refused = client.put("/api/me/settings", json={"activeProvider": "anthropic"})
    unknown = client.put("/api/me/settings", json={"activeProvider": "nope"})

    assert refused.status_code == 409
    assert refused.get_json()["code"] == "api_key_required"
    assert unknown.status_code == 400


def test_user_can_switch_the_provider_in_use_and_clear_it(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)
    client.put("/api/me/api-keys/openrouter", json={"apiKey": SENTINEL_KEY})
    client.put("/api/me/api-keys/anthropic", json={"apiKey": "sk-ant-second-key-5678"})

    switched = client.put("/api/me/settings", json={"activeProvider": "anthropic"}).get_json()
    cleared = client.put("/api/me/settings", json={"activeProvider": None}).get_json()

    assert switched["activeProvider"] == "anthropic"
    assert cleared["activeProvider"] is None


def test_deleting_the_key_in_use_clears_the_choice(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    client = make_client(store)
    client.put("/api/me/api-keys/openrouter", json={"apiKey": SENTINEL_KEY})

    client.delete("/api/me/api-keys/openrouter")

    settings = client.get("/api/me/settings").get_json()
    assert settings["activeProvider"] is None
    assert settings["providers"][0] == {"provider": "anthropic", "configured": False, "last4": None}


def test_settings_are_per_user(monkeypatch):
    store = InMemorySessionStore()
    patch_validation(monkeypatch, AcceptingProvider())
    make_client(store).put("/api/me/api-keys/openrouter", json={"apiKey": SENTINEL_KEY})
    other = sign_in(create_app(store=store).test_client(), user_id="user-2")

    assert other.get("/api/me/settings").get_json()["activeProvider"] is None
