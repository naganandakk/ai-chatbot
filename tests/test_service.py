from types import SimpleNamespace

from core.chat_core.service import ChatService
from core.chat_core.store import SessionStore


class FakeMessages:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return [
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text="Hello"),
            ),
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text=" world"),
            ),
        ]


class FakeClaudeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def test_stream_reply_saves_user_and_assistant_messages():
    store = SessionStore()
    session = store.create()
    client = FakeClaudeClient()
    service = ChatService(store, client=client)

    chunks = list(service.stream_reply(session.id, "Say hello"))

    saved_session = store.get(session.id)

    assert chunks == ["Hello", " world"]
    assert saved_session is not None
    assert [message.role for message in saved_session.messages] == ["user", "assistant"]
    assert saved_session.messages[1].content == "Hello world"
    assert client.messages.requests[0]["stream"] is True
    assert client.messages.requests[0]["messages"] == [
        {"role": "user", "content": "Say hello"}
    ]


def test_stream_reply_uses_requested_model_and_records_it():
    store = SessionStore()
    session = store.create()
    client = FakeClaudeClient()
    service = ChatService(store, client=client)

    list(service.stream_reply(session.id, "Say hello", model="claude-opus-5-5"))

    saved_session = store.get(session.id)

    assert client.messages.requests[0]["model"] == "claude-opus-5-5"
    assert saved_session is not None
    assert saved_session.messages[1].model == "claude-opus-5-5"
    assert saved_session.to_dict()["messages"][1]["model"] == "claude-opus-5-5"


def test_stream_reply_falls_back_to_default_model_when_missing():
    store = SessionStore()
    session = store.create()
    client = FakeClaudeClient()
    service = ChatService(store, client=client)

    list(service.stream_reply(session.id, "Say hello", model="  "))

    saved_session = store.get(session.id)

    assert client.messages.requests[0]["model"] == "test-model"
    assert saved_session is not None
    assert saved_session.messages[1].model == "test-model"


def test_stream_reply_rejects_empty_messages():
    store = SessionStore()
    session = store.create()
    service = ChatService(store, client=FakeClaudeClient())

    try:
        list(service.stream_reply(session.id, "   "))
    except ValueError as error:
        assert str(error) == "Message cannot be empty"
    else:
        raise AssertionError("Expected ValueError")