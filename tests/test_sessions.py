from backend.app import create_app
from core.chat_core.store import InMemorySessionStore


def test_create_and_list_sessions():
    app = create_app()
    client = app.test_client()

    created_response = client.post("/api/sessions")

    assert created_response.status_code == 201
    created_session = created_response.get_json()
    assert created_session["title"] == "New chat"
    assert created_session["messages"] == []

    list_response = client.get("/api/sessions")

    assert list_response.status_code == 200
    assert list_response.get_json() == [
        {
            "id": created_session["id"],
            "title": "New chat",
            "createdAt": created_session["createdAt"],
            "updatedAt": created_session["updatedAt"],
        }
    ]

def test_get_and_clear_session():
    app = create_app()
    client = app.test_client()

    created_session = client.post("/api/sessions").get_json()
    session_id = created_session["id"]

    get_response = client.get(f"/api/sessions/{session_id}")

    assert get_response.status_code == 200
    assert get_response.get_json()["id"] == session_id

    clear_response = client.delete(f"/api/sessions/{session_id}/messages")

    assert clear_response.status_code == 200
    assert clear_response.get_json()["messages"] == []
    assert clear_response.get_json()["title"] == "New chat"


def test_get_missing_session_returns_not_found():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/sessions/does-not-exist")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Session not found"}

def test_session_response_includes_usage_totals_but_list_does_not():
    store = InMemorySessionStore()
    session = store.create()
    store.add_message(
        session.id,
        "assistant",
        "Hi",
        model="claude-sonnet-5-5",
        usage='{"input_tokens": 12, "output_tokens": 5, "cost_usd": 0.5}',
    )
    client = create_app(store=store).test_client()

    get_body = client.get(f"/api/sessions/{session.id}").get_json()
    list_body = client.get("/api/sessions").get_json()

    assert get_body["usage"]["costUsd"] == 0.5
    assert get_body["usage"]["inputTokens"] == 12
    assert "usage" not in list_body[0]
