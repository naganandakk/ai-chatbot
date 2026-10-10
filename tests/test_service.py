import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from core.chat_core.service import ChatService, ProviderStreamError
from core.chat_core.settings import Settings
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


def openrouter_sse(*payloads: dict) -> str:
    events = "".join(f"data: {json.dumps(payload)}\n\n" for payload in payloads)
    return events + "data: [DONE]\n\n"


def openrouter_chunk(content: str = "", annotations: list[dict] | None = None) -> dict:
    delta = {"content": content, "role": "assistant"}
    if annotations:
        delta["annotations"] = annotations

    return {
        "id": "gen-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "anthropic/claude-haiku-4.5",
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    }


def url_citation(title: str, url: str) -> dict:
    return {
        "type": "url_citation",
        "url_citation": {"url": url, "title": title, "start_index": 0, "end_index": 0},
    }


def openrouter_transport(events: list[dict], requests: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(openrouter_sse(*events).encode()),
        )

    return httpx.MockTransport(handler)


def openrouter_settings() -> Settings:
    return Settings(
        provider="openrouter",
        api_key="openrouter-key",
        model="anthropic/claude-haiku-4.5",
    )


def test_openrouter_stream_reply_uses_openrouter_sdk_and_saves_messages():
    store = SessionStore()
    session = store.create()
    requests: list[dict] = []
    transport = openrouter_transport(
        [openrouter_chunk("Hello"), openrouter_chunk(" world")],
        requests,
    )
    service = ChatService(store, settings=openrouter_settings(), openrouter_transport=transport)

    chunks = list(service.stream_reply(session.id, "Say hello"))

    saved_session = store.get(session.id)

    assert chunks == ["Hello", " world"]
    assert saved_session is not None
    assert saved_session.messages[1].content == "Hello world"
    assert saved_session.messages[1].model == "anthropic/claude-haiku-4.5"
    assert requests[0]["stream"] is True
    assert requests[0]["max_completion_tokens"] == 2048
    assert requests[0]["messages"] == [{"role": "user", "content": "Say hello"}]
    assert "plugins" not in requests[0]


def test_openrouter_web_search_tool_enables_web_plugin():
    store = SessionStore()
    session = store.create()
    requests: list[dict] = []
    transport = openrouter_transport([openrouter_chunk("Hi")], requests)
    service = ChatService(
        store,
        settings=openrouter_settings(),
        openrouter_transport=transport,
        tools_enabled=["web_search"],
    )

    list(service.stream_reply(session.id, "Latest news"))

    assert requests[0]["plugins"] == [{"id": "web"}]


def test_openrouter_url_citations_are_saved_as_sources():
    store = SessionStore()
    session = store.create()
    requests: list[dict] = []
    citation = url_citation("Python Downloads", "https://www.python.org/downloads/")
    transport = openrouter_transport(
        [
            openrouter_chunk("Python 3.15 is out."),
            openrouter_chunk("", annotations=[citation]),
            openrouter_chunk("", annotations=[citation]),
        ],
        requests,
    )
    service = ChatService(
        store,
        settings=openrouter_settings(),
        openrouter_transport=transport,
        tools_enabled=["web_search"],
    )

    list(service.stream_reply(session.id, "Latest Python?"))

    saved_message = store.get(session.id).messages[1]
    assert json.loads(saved_message.sources) == [
        {"title": "Python Downloads", "url": "https://www.python.org/downloads/"}
    ]
    assert saved_message.to_dict()["sources"] == [
        {"title": "Python Downloads", "url": "https://www.python.org/downloads/"}
    ]


def test_openrouter_stream_error_raises_and_skips_assistant_message():
    store = SessionStore()
    session = store.create()
    requests: list[dict] = []
    error_chunk = {
        "id": "gen-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "anthropic/claude-haiku-4.5",
        "error": {"code": 502, "message": "Upstream overloaded"},
        "choices": [],
    }
    transport = openrouter_transport(
        [openrouter_chunk("Par"), error_chunk],
        requests,
    )
    service = ChatService(store, settings=openrouter_settings(), openrouter_transport=transport)

    with pytest.raises(ProviderStreamError, match="Upstream overloaded"):
        list(service.stream_reply(session.id, "Say hello"))

    saved_session = store.get(session.id)
    assert [message.role for message in saved_session.messages] == ["user"]


def test_openrouter_client_is_reused_and_citations_do_not_leak_between_replies():
    store = SessionStore()
    session = store.create()
    requests: list[dict] = []
    first = url_citation("First", "https://example.com/first")
    second = url_citation("Second", "https://example.com/second")
    replies = iter([
        [openrouter_chunk("One", annotations=[first])],
        [openrouter_chunk("Two", annotations=[second])],
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(openrouter_sse(*next(replies)).encode()),
        )

    service = ChatService(
        store,
        settings=openrouter_settings(),
        openrouter_transport=httpx.MockTransport(handler),
    )

    list(service.stream_reply(session.id, "First question"))
    client = service._openrouter
    list(service.stream_reply(session.id, "Second question"))

    messages = store.get(session.id).messages
    assert service._openrouter is client
    assert len(requests) == 2
    assert json.loads(messages[1].sources) == [{"title": "First", "url": "https://example.com/first"}]
    assert json.loads(messages[3].sources) == [{"title": "Second", "url": "https://example.com/second"}]


def test_concurrent_openrouter_replies_keep_their_own_citations():
    store = SessionStore()
    sessions = [store.create(), store.create()]
    citations = {
        "alpha": url_citation("Alpha", "https://example.com/alpha"),
        "beta": url_citation("Beta", "https://example.com/beta"),
    }
    # Both requests must be in flight before either stream is read.
    in_flight = threading.Barrier(2)

    def handler(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["messages"][-1]["content"]
        in_flight.wait(timeout=5)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(openrouter_sse(
                openrouter_chunk(prompt, annotations=[citations[prompt]]),
            ).encode()),
        )

    service = ChatService(
        store,
        settings=openrouter_settings(),
        openrouter_transport=httpx.MockTransport(handler),
    )

    def run(session_id: str, prompt: str) -> None:
        "".join(service.stream_reply(session_id, prompt))

    threads = [
        threading.Thread(target=run, args=(session.id, prompt))
        for session, prompt in zip(sessions, ["alpha", "beta"])
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    for session, prompt in zip(sessions, ["alpha", "beta"]):
        assistant = store.get(session.id).messages[1]
        citation = citations[prompt]["url_citation"]
        assert json.loads(assistant.sources) == [
            {"title": citation["title"], "url": citation["url"]}
        ]
