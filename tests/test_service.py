import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from core.chat_core.providers import (
    AnthropicProvider,
    Citation,
    OpenRouterProvider,
    ProviderError,
    ProviderStreamError,
    ReplyReset,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
    Usage,
)
from core.chat_core.service import ChatService
from core.chat_core.settings import DEFAULT_MAX_TOKENS, Settings
from core.chat_core.store import InMemorySessionStore
from tests.support import USER_ID


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


class FakeProvider:
    def __init__(self, events: list) -> None:
        self.events = events
        self.calls: list[dict] = []

    def stream(self, *, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        yield from self.events


def anthropic_settings() -> Settings:
    return Settings(provider="anthropic", api_key="test-key", model="test-model")


def anthropic_service(store, client) -> ChatService:
    return ChatService(
        store,
        provider=AnthropicProvider(api_key="test-key", client=client),
        settings=anthropic_settings(),
    )


def test_stream_reply_saves_user_and_assistant_messages():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = FakeClaudeClient()
    service = anthropic_service(store, client)

    chunks = list(service.stream_reply(USER_ID, session.id, "Say hello"))

    saved_session = store.get(USER_ID, session.id)

    assert chunks == ["Hello", " world"]
    assert saved_session is not None
    assert [message.role for message in saved_session.messages] == ["user", "assistant"]
    assert saved_session.messages[1].content == "Hello world"
    assert client.messages.requests[0]["stream"] is True
    assert client.messages.requests[0]["messages"] == [
        {"role": "user", "content": "Say hello"}
    ]


def drain(generator):
    chunks = []
    while True:
        try:
            chunks.append(next(generator))
        except StopIteration as finished:
            return chunks, finished.value


def test_stream_reply_returns_saved_assistant_message_with_sources():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    provider = FakeProvider([
        TextDelta("Hi"),
        Citation(title="Docs", url="https://example.com/docs"),
        ReplyTruncated(),
    ])
    service = ChatService(store, provider=provider, settings=anthropic_settings())

    chunks, reply = drain(service.stream_reply(USER_ID, session.id, "Hello"))

    assert chunks == ["Hi"]
    assert reply.role == "assistant"
    assert reply.content == "Hi"
    assert reply.truncated is True
    assert reply.to_dict()["sources"] == [{"title": "Docs", "url": "https://example.com/docs"}]


def test_stream_reply_uses_requested_model_and_records_it():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = FakeClaudeClient()
    service = anthropic_service(store, client)

    list(service.stream_reply(USER_ID, session.id, "Say hello", model="claude-opus-5-5"))

    saved_session = store.get(USER_ID, session.id)

    assert client.messages.requests[0]["model"] == "claude-opus-5-5"
    assert saved_session is not None
    assert saved_session.messages[1].model == "claude-opus-5-5"
    assert saved_session.to_dict()["messages"][1]["model"] == "claude-opus-5-5"


def test_stream_reply_falls_back_to_default_model_when_missing():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = FakeClaudeClient()
    service = anthropic_service(store, client)

    list(service.stream_reply(USER_ID, session.id, "Say hello", model="  "))

    saved_session = store.get(USER_ID, session.id)

    assert client.messages.requests[0]["model"] == "test-model"
    assert saved_session is not None
    assert saved_session.messages[1].model == "test-model"


def test_stream_reply_rejects_empty_messages():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    service = anthropic_service(store, FakeClaudeClient())

    try:
        list(service.stream_reply(USER_ID, session.id, "   "))
    except ValueError as error:
        assert str(error) == "Message cannot be empty"
    else:
        raise AssertionError("Expected ValueError")


def test_service_saves_events_from_any_provider():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    provider = FakeProvider([
        TextDelta("Hi"),
        Citation(title="Docs", url="https://example.com/docs"),
        TextDelta("!"),
    ])
    service = ChatService(
        store,
        provider=provider,
        settings=anthropic_settings(),
    )

    chunks = list(service.stream_reply(USER_ID, session.id, "Hello", tools=["web_search"]))

    assistant = store.get(USER_ID, session.id).messages[1]
    assert chunks == ["Hi", "!"]
    assert assistant.content == "Hi!"
    assert json.loads(assistant.sources) == [
        {"title": "Docs", "url": "https://example.com/docs"}
    ]
    assert provider.calls == [
        {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": ["web_search"],
        }
    ]


def test_anthropic_maps_enabled_tools_to_server_tools():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = FakeClaudeClient()
    service = anthropic_service(store, client)

    list(service.stream_reply(USER_ID, session.id, "Latest news", tools=["web_search"]))

    assert client.messages.requests[0]["tools"] == [{"type": "web_search"}]


class SearchingMessages:
    def create(self, **kwargs):
        return [
            SimpleNamespace(
                type="content_block_start",
                content_block=SimpleNamespace(type="text"),
            ),
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text="Let me search."),
            ),
            SimpleNamespace(
                type="content_block_start",
                content_block=SimpleNamespace(type="server_tool_use"),
            ),
            SimpleNamespace(
                type="content_block_start",
                content_block=SimpleNamespace(type="text"),
            ),
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text="It is sunny."),
            ),
        ]


def test_anthropic_narration_before_web_search_is_dropped_from_reply():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = SimpleNamespace(messages=SearchingMessages())
    service = anthropic_service(store, client)

    chunks = list(service.stream_reply(USER_ID, session.id, "Weather?", tools=["web_search"]))

    assistant = store.get(USER_ID, session.id).messages[1]
    assert chunks == ["Let me search.", ReplyReset(), "It is sunny."]
    assert assistant.content == "It is sunny."


def test_stream_reply_reset_clears_text_and_sources_before_it():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    provider = FakeProvider([
        TextDelta("Searching..."),
        Citation(title="Old", url="https://example.com/old"),
        ReplyReset(),
        TextDelta("Answer"),
        Citation(title="New", url="https://example.com/new"),
    ])
    service = ChatService(store, provider=provider, settings=anthropic_settings())

    chunks = list(service.stream_reply(USER_ID, session.id, "Hello"))

    assistant = store.get(USER_ID, session.id).messages[1]
    assert chunks == ["Searching...", ReplyReset(), "Answer"]
    assert assistant.content == "Answer"
    assert json.loads(assistant.sources) == [{"title": "New", "url": "https://example.com/new"}]


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


def openrouter_service(store, transport) -> ChatService:
    return ChatService(
        store,
        provider=OpenRouterProvider(api_key="openrouter-key", transport=transport),
        settings=openrouter_settings(),
    )


def test_openrouter_stream_reply_uses_openrouter_sdk_and_saves_messages():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    transport = openrouter_transport(
        [openrouter_chunk("Hello"), openrouter_chunk(" world")],
        requests,
    )
    service = openrouter_service(store, transport)

    chunks = list(service.stream_reply(USER_ID, session.id, "Say hello"))

    saved_session = store.get(USER_ID, session.id)

    assert chunks == ["Hello", " world"]
    assert saved_session is not None
    assert saved_session.messages[1].content == "Hello world"
    assert saved_session.messages[1].model == "anthropic/claude-haiku-4.5"
    assert requests[0]["stream"] is True
    assert requests[0]["max_completion_tokens"] == DEFAULT_MAX_TOKENS
    assert requests[0]["reasoning"] == {"effort": "none"}
    assert requests[0]["messages"] == [{"role": "user", "content": "Say hello"}]
    assert "plugins" not in requests[0]


def test_openrouter_retries_with_low_reasoning_when_model_requires_it():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    efforts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        effort = json.loads(request.content)["reasoning"]["effort"]
        efforts.append(effort)
        if effort == "none":
            return httpx.Response(400, json={"error": {
                "message": "Reasoning is mandatory for this endpoint and cannot be disabled.",
                "code": 400,
            }})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(openrouter_sse(openrouter_chunk("Hi")).encode()),
        )

    provider = OpenRouterProvider(api_key="test-key", transport=httpx.MockTransport(handler))
    service = ChatService(store, provider=provider, settings=openrouter_settings())

    assert "".join(service.stream_reply(USER_ID, session.id, "Hello")) == "Hi"
    assert "".join(service.stream_reply(USER_ID, session.id, "Again")) == "Hi"

    # The first reply tries "none", then "low". The second goes straight to "low".
    assert efforts == ["none", "low", "low"]


def test_openrouter_sends_low_reasoning_first_for_known_mandatory_models():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    transport = openrouter_transport([openrouter_chunk("Hi")], requests)
    service = openrouter_service(store, transport)

    assert "".join(service.stream_reply(USER_ID, session.id, "Hello", model="~anthropic/claude-sonnet-latest")) == "Hi"

    assert [request["reasoning"] for request in requests] == [{"effort": "low"}]


def test_openrouter_uses_mandatory_reasoning_from_model_list_on_first_request():
    listing_provider = OpenRouterProvider(api_key="openrouter-key")
    mandatory_model = SimpleNamespace(
        id="test/mandatory-reasoning-model",
        name="Test: Mandatory Reasoning",
        reasoning=SimpleNamespace(mandatory=True, supported_efforts=["high", "medium"]),
    )
    listing_provider._client = SimpleNamespace(models=SimpleNamespace(
        list_for_user=lambda *, security: SimpleNamespace(
            result=SimpleNamespace(data=[mandatory_model]),
        ),
    ))
    listing_provider.list_models()

    requests: list[dict] = []
    provider = OpenRouterProvider(
        api_key="openrouter-key",
        transport=openrouter_transport([openrouter_chunk("Hi")], requests),
    )
    events = provider.stream(
        model="test/mandatory-reasoning-model",
        messages=[{"role": "user", "content": "Hello"}],
        tools=[],
    )

    assert "".join(event.text for event in events if isinstance(event, TextDelta)) == "Hi"
    # The lowest supported effort is sent first, so "none" is never tried
    assert [request["reasoning"] for request in requests] == [{"effort": "medium"}]


def test_warm_up_logs_and_keeps_starting_when_model_list_fails():
    class FailingProvider:
        def list_models(self):
            raise ProviderError("upstream down")

    service = ChatService(InMemorySessionStore(), provider=FailingProvider(), settings=openrouter_settings())

    service.warm_up()


def test_openrouter_web_search_tells_model_not_to_narrate_the_search():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    transport = openrouter_transport([openrouter_chunk("Sunny today.")], requests)
    service = openrouter_service(store, transport)

    list(service.stream_reply(USER_ID, session.id, "Weather?", tools=["web_search"]))

    system_message = requests[0]["messages"][0]
    assert system_message["role"] == "system"
    assert "Do not say that you are going to search" in system_message["content"]
    assert requests[0]["messages"][1] == {"role": "user", "content": "Weather?"}


def test_openrouter_web_search_tool_enables_web_plugin():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    transport = openrouter_transport([openrouter_chunk("Hi")], requests)
    service = openrouter_service(store, transport)

    list(service.stream_reply(USER_ID, session.id, "Latest news", tools=["web_search"]))

    assert requests[0]["plugins"] == [{"id": "web"}]


def test_openrouter_url_citations_are_saved_as_sources():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
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
    service = openrouter_service(store, transport)

    list(service.stream_reply(USER_ID, session.id, "Latest Python?", tools=["web_search"]))

    saved_message = store.get(USER_ID, session.id).messages[1]
    assert json.loads(saved_message.sources) == [
        {"title": "Python Downloads", "url": "https://www.python.org/downloads/"}
    ]
    assert saved_message.to_dict()["sources"] == [
        {"title": "Python Downloads", "url": "https://www.python.org/downloads/"}
    ]


def test_openrouter_stream_error_raises_and_skips_assistant_message():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
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
    service = openrouter_service(store, transport)

    with pytest.raises(ProviderStreamError, match="Upstream overloaded"):
        list(service.stream_reply(USER_ID, session.id, "Say hello"))

    saved_session = store.get(USER_ID, session.id)
    assert [message.role for message in saved_session.messages] == ["user"]


def test_openrouter_client_is_reused_and_citations_do_not_leak_between_replies():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
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

    service = openrouter_service(store, httpx.MockTransport(handler))
    client = service.provider._client

    list(service.stream_reply(USER_ID, session.id, "First question"))
    list(service.stream_reply(USER_ID, session.id, "Second question"))

    messages = store.get(USER_ID, session.id).messages
    assert service.provider._client is client
    assert len(requests) == 2
    assert json.loads(messages[1].sources) == [{"title": "First", "url": "https://example.com/first"}]
    assert json.loads(messages[3].sources) == [{"title": "Second", "url": "https://example.com/second"}]


def test_concurrent_openrouter_replies_keep_their_own_citations():
    store = InMemorySessionStore()
    sessions = [store.create(USER_ID), store.create(USER_ID)]
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

    service = openrouter_service(store, httpx.MockTransport(handler))

    def run(session_id: str, prompt: str) -> None:
        "".join(service.stream_reply(USER_ID, session_id, prompt))

    threads = [
        threading.Thread(target=run, args=(session.id, prompt))
        for session, prompt in zip(sessions, ["alpha", "beta"])
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    for session, prompt in zip(sessions, ["alpha", "beta"]):
        assistant = store.get(USER_ID, session.id).messages[1]
        citation = citations[prompt]["url_citation"]
        assert json.loads(assistant.sources) == [
            {"title": citation["title"], "url": citation["url"]}
        ]


def test_openrouter_reply_cut_off_before_any_text_raises_and_skips_assistant_message():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    cut_off = openrouter_chunk("")
    cut_off["choices"][0]["finish_reason"] = "length"
    transport = openrouter_transport([cut_off], requests)
    service = openrouter_service(store, transport)

    with pytest.raises(TruncatedReplyError, match="token limit"):
        list(service.stream_reply(USER_ID, session.id, "Explain everything"))

    saved_session = store.get(USER_ID, session.id)
    assert [message.role for message in saved_session.messages] == ["user"]


class TruncatedMessages:
    def create(self, **kwargs):
        return [
            SimpleNamespace(
                type="message_delta",
                delta=SimpleNamespace(stop_reason="max_tokens"),
                usage=SimpleNamespace(output_tokens=8192, server_tool_use=None),
            ),
        ]


def test_anthropic_reply_cut_off_before_any_text_raises():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = SimpleNamespace(messages=TruncatedMessages())
    service = anthropic_service(store, client)

    with pytest.raises(TruncatedReplyError):
        list(service.stream_reply(USER_ID, session.id, "Explain everything"))

    assert [message.role for message in store.get(USER_ID, session.id).messages] == ["user"]


def test_openrouter_reply_cut_off_after_text_is_saved_as_truncated():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    cut_off = openrouter_chunk("Partial answer")
    cut_off["choices"][0]["finish_reason"] = "length"
    transport = openrouter_transport([cut_off], requests)
    service = openrouter_service(store, transport)

    chunks = list(service.stream_reply(USER_ID, session.id, "Explain everything"))

    assistant = store.get(USER_ID, session.id).messages[1]
    assert chunks == ["Partial answer"]
    assert assistant.content == "Partial answer"
    assert assistant.truncated is True


def test_complete_openrouter_reply_is_not_truncated():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    transport = openrouter_transport([openrouter_chunk("Done")], [])
    service = openrouter_service(store, transport)

    list(service.stream_reply(USER_ID, session.id, "Hi"))

    assert store.get(USER_ID, session.id).messages[1].truncated is False


class TruncatedAfterTextMessages:
    def create(self, **kwargs):
        return [
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text="Partial"),
            ),
            SimpleNamespace(
                type="message_delta",
                delta=SimpleNamespace(stop_reason="max_tokens"),
                usage=SimpleNamespace(output_tokens=8192, server_tool_use=None),
            ),
        ]


def test_anthropic_reply_cut_off_after_text_is_saved_as_truncated():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    client = SimpleNamespace(messages=TruncatedAfterTextMessages())
    service = anthropic_service(store, client)

    chunks = list(service.stream_reply(USER_ID, session.id, "Explain everything"))

    assistant = store.get(USER_ID, session.id).messages[1]
    assert chunks == ["Partial"]
    assert assistant.truncated is True


def test_provider_sends_configured_max_tokens():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    transport = openrouter_transport([openrouter_chunk("Hi")], requests)
    provider = OpenRouterProvider(api_key="openrouter-key", transport=transport, max_tokens=512)
    service = ChatService(store, provider=provider, settings=openrouter_settings())

    list(service.stream_reply(USER_ID, session.id, "Hello"))

    assert requests[0]["max_completion_tokens"] == 512


def test_anthropic_reply_reports_tokens_and_cost():
    class UsageMessages:
        def create(self, **kwargs):
            return [
                SimpleNamespace(
                    type="message_start",
                    message=SimpleNamespace(usage=SimpleNamespace(
                        input_tokens=1000,
                        cache_creation_input_tokens=200,
                        cache_read_input_tokens=300,
                    )),
                ),
                SimpleNamespace(
                    type="content_block_delta",
                    delta=SimpleNamespace(type="text_delta", text="Hi"),
                ),
                SimpleNamespace(
                    type="message_delta",
                    delta=SimpleNamespace(stop_reason="end_turn"),
                    usage=SimpleNamespace(
                        output_tokens=50,
                        server_tool_use=SimpleNamespace(web_search_requests=2),
                    ),
                ),
            ]

    store = InMemorySessionStore()
    session = store.create(USER_ID)
    service = anthropic_service(store, SimpleNamespace(messages=UsageMessages()))

    list(service.stream_reply(USER_ID, session.id, "Hello", model="claude-sonnet-5-5"))

    usage = store.get(USER_ID, session.id).to_dict()["messages"][1]["usage"]
    # Sonnet 5.5: 1000 input at $2, 200 cache writes at $2.50, 300 cache reads at $0.10,
    # 50 output at $10, plus 2 searches at $0.01
    assert usage == {
        "inputTokens": 1500,
        "outputTokens": 50,
        "costUsd": pytest.approx(0.02303),
        "cacheReadTokens": 300,
        "cacheWriteTokens": 200,
    }


def test_anthropic_unknown_model_reports_tokens_without_cost():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    provider = FakeProvider([Usage(input_tokens=12, output_tokens=3, cost_usd=None)])
    service = ChatService(store, provider=provider, settings=anthropic_settings())

    list(service.stream_reply(USER_ID, session.id, "Hello"))

    usage = store.get(USER_ID, session.id).to_dict()["messages"][1]["usage"]
    assert usage == {
        "inputTokens": 12,
        "outputTokens": 3,
        "costUsd": None,
        "cacheReadTokens": 0,
        "cacheWriteTokens": 0,
    }


def test_openrouter_reply_reports_cost_from_final_chunk():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    requests: list[dict] = []
    final_chunk = {
        "id": "gen-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "anthropic/claude-haiku-4.5",
        "choices": [],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 5,
            "total_tokens": 17,
            "cost": 0.00042,
        },
    }
    transport = openrouter_transport([openrouter_chunk("Hi"), final_chunk], requests)
    service = openrouter_service(store, transport)

    assert "".join(service.stream_reply(USER_ID, session.id, "Hello")) == "Hi"

    usage = store.get(USER_ID, session.id).to_dict()["messages"][1]["usage"]
    assert usage == {
        "inputTokens": 12,
        "outputTokens": 5,
        "costUsd": 0.00042,
        "cacheReadTokens": 0,
        "cacheWriteTokens": 0,
    }


def test_usage_survives_a_reply_reset_because_the_tokens_were_billed():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    provider = FakeProvider([
        Usage(input_tokens=10, output_tokens=4, cost_usd=0.5),
        TextDelta("Searching..."),
        ReplyReset(),
        TextDelta("Answer"),
    ])
    service = ChatService(store, provider=provider, settings=anthropic_settings())

    list(service.stream_reply(USER_ID, session.id, "Hello"))

    assistant = store.get(USER_ID, session.id).messages[1]
    assert assistant.content == "Answer"
    assert assistant.to_dict()["usage"] == {
        "inputTokens": 10,
        "outputTokens": 4,
        "costUsd": 0.5,
        "cacheReadTokens": 0,
        "cacheWriteTokens": 0,
    }


def test_reply_without_usage_event_saves_no_usage():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    service = ChatService(
        store,
        provider=FakeProvider([TextDelta("Hi")]),
        settings=anthropic_settings(),
    )

    list(service.stream_reply(USER_ID, session.id, "Hello"))

    assert store.get(USER_ID, session.id).messages[1].to_dict()["usage"] is None


def test_reply_saves_time_taken_in_milliseconds():
    store = InMemorySessionStore()
    session = store.create(USER_ID)
    service = ChatService(
        store,
        provider=FakeProvider([TextDelta("Hi")]),
        settings=anthropic_settings(),
    )

    list(service.stream_reply(USER_ID, session.id, "Hello"))

    duration_ms = store.get(USER_ID, session.id).to_dict()["messages"][1]["durationMs"]
    assert isinstance(duration_ms, int)
    assert duration_ms >= 0
