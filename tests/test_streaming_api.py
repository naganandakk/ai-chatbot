from backend.app import create_app
from core.chat_core.store import InMemorySessionStore, SessionStore


class FakeChatService:
    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def stream_reply(self, session_id: str, prompt: str, model: str | None = None):
        self.store.add_message(session_id, "user", prompt)
        yield "Hello"
        yield " world"
        self.store.add_message(session_id, "assistant", "Hello world", "[]", model or "")


def test_streaming_message_endpoint():
    store = InMemorySessionStore()
    app = create_app(
        store=store,
        chat_service=FakeChatService(store),
    )
    client = app.test_client()
    session = client.post("/api/sessions").get_json()

    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"message": "Say hello"},
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.content_type.startswith("text/event-stream")
    assert 'event: delta\ndata: {"text": "Hello"}' in body
    assert 'event: delta\ndata: {"text": " world"}' in body
    assert "event: done\ndata: {}" in body

    saved_session = client.get(f"/api/sessions/{session['id']}").get_json()
    assert [message["role"] for message in saved_session["messages"]] == [
        "user",
        "assistant",
    ]
    assert saved_session["messages"][1]["content"] == "Hello world"

def test_streaming_endpoint_reports_empty_message_error():
    app = create_app()
    client = app.test_client()
    session = client.post("/api/sessions").get_json()

    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"message": "   "},
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.content_type.startswith("text/event-stream")
    assert "event: error" in body
    assert '"message": "Message cannot be empty"' in body

def test_streaming_endpoint_passes_truncated_reply_message_to_client():
    from core.chat_core.providers import TruncatedReplyError

    class TruncatingChatService:
        def stream_reply(self, session_id: str, prompt: str, model: str | None = None):
            raise TruncatedReplyError()
            yield

    app = create_app(chat_service=TruncatingChatService())
    client = app.test_client()
    session = client.post("/api/sessions").get_json()

    body = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"message": "Explain everything"},
    ).get_data(as_text=True)

    assert "event: error" in body
    assert "The model used its token limit before writing a reply" in body
