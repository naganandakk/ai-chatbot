from backend.app import create_app
from core.chat_core.store import InMemorySessionStore
from tests.support import sign_in


def test_api_responses_are_not_cached_and_cannot_run_as_a_page():
    client = sign_in(create_app(store=InMemorySessionStore()).test_client())

    response = client.get("/api/sessions")

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_key_saves_and_deletes_are_recorded_without_the_key(monkeypatch):
    from backend.app import api_keys
    from core.chat_core.providers import ModelInfo

    class Accepting:
        def list_models(self):
            return [ModelInfo(id="m", name="M")]

        def close(self):
            pass

    monkeypatch.setattr(api_keys, "create_provider_for", lambda *args, **kwargs: Accepting())
    store = InMemorySessionStore()
    client = sign_in(create_app(store=store).test_client())

    client.put("/api/me/api-keys/anthropic", json={"apiKey": "sk-ant-audit-secret-9999"})
    client.delete("/api/me/api-keys/anthropic")

    events = store.list_audit_events("user-1")
    assert [event.action for event in events] == ["api_key.saved", "api_key.deleted"]
    assert all("sk-ant-audit-secret" not in repr(event) for event in events)
