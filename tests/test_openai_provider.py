import json
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from core.chat_core.providers import (
    OpenAIProvider,
    ProviderError,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
    Usage,
    create_provider,
)
from core.chat_core.providers.openai_provider import _openai_message
from core.chat_core.settings import Settings


def chunk(content: str | None = None, finish_reason: str | None = None) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "delta": {"content": content}, "finish_reason": finish_reason}
        ],
    }


def usage_chunk(prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "prompt_tokens_details": {"cached_tokens": cached_tokens},
        },
    }


def sse(*payloads: dict) -> str:
    lines = [f"data: {json.dumps(payload)}\n\n" for payload in payloads]
    return "".join(lines) + "data: [DONE]\n\n"


def provider_with_transport(transport: httpx.MockTransport) -> OpenAIProvider:
    # The real SDK runs over a mock transport. Retries are off so an error response fails at once.
    client = OpenAI(
        api_key="sk-test",
        max_retries=0,
        http_client=httpx.Client(transport=transport),
    )
    return OpenAIProvider(api_key="sk-test", client=client, max_tokens=512)


def streaming_transport(payloads: list[dict], requests: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(sse(*payloads).encode()),
        )

    return httpx.MockTransport(handler)


def test_streams_text_and_usage_through_openai_sdk():
    requests: list[dict] = []
    transport = streaming_transport(
        [chunk("Hel"), chunk("lo"), chunk(finish_reason="stop"), usage_chunk(10, 2, cached_tokens=4)],
        requests,
    )
    provider = provider_with_transport(transport)

    events = list(
        provider.stream(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hi"}],
            tools=["web_search"],
        )
    )

    assert events[:2] == [TextDelta("Hel"), TextDelta("lo")]
    usage = events[2]
    assert isinstance(usage, Usage)
    assert (usage.input_tokens, usage.output_tokens, usage.cache_read_tokens) == (10, 2, 4)
    # 6 uncached tokens at $0.15, 4 cached at $0.075, and 2 output at $0.60, per million
    assert usage.cost_usd == pytest.approx((6 * 0.15 + 4 * 0.075 + 2 * 0.6) / 1e6)
    assert requests[0]["model"] == "gpt-4o-mini"
    assert requests[0]["max_completion_tokens"] == 512
    assert requests[0]["stream"] is True
    assert requests[0]["stream_options"] == {"include_usage": True}
    assert requests[0]["messages"] == [{"role": "user", "content": "Hi"}]


def test_reply_cut_off_at_token_limit_after_text_is_marked_truncated():
    transport = streaming_transport(
        [chunk("Partial answer"), chunk(finish_reason="length")], []
    )
    provider = provider_with_transport(transport)

    events = list(provider.stream(model="gpt-4o-mini", messages=[], tools=[]))

    assert events == [TextDelta("Partial answer"), ReplyTruncated()]


def test_reply_cut_off_at_token_limit_before_text_raises():
    transport = streaming_transport([chunk(finish_reason="length")], [])
    provider = provider_with_transport(transport)

    with pytest.raises(TruncatedReplyError):
        list(provider.stream(model="gpt-4o-mini", messages=[], tools=[]))


def test_sdk_error_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Bad model", "type": "invalid"}})

    provider = provider_with_transport(httpx.MockTransport(handler))

    with pytest.raises(ProviderError, match="Bad model"):
        list(provider.stream(model="nope", messages=[], tools=[]))


def test_list_models_maps_sdk_models_to_id_and_name():
    models = [SimpleNamespace(id="gpt-4o-mini"), SimpleNamespace(id="gpt-4.1")]
    client = SimpleNamespace(models=SimpleNamespace(list=lambda: models))
    provider = OpenAIProvider(api_key="sk-test", client=client)

    assert [(model.id, model.name) for model in provider.list_models()] == [
        ("gpt-4o-mini", "gpt-4o-mini"),
        ("gpt-4.1", "gpt-4.1"),
    ]


def test_files_are_sent_as_data_urls_in_content_parts():
    message = _openai_message({
        "role": "user",
        "content": [
            {"type": "text", "text": "Read this"},
            {"type": "image", "filename": "a.png", "media_type": "image/png", "data": b"png"},
            {"type": "document", "filename": "a.pdf", "media_type": "application/pdf", "data": b"pdf"},
        ],
    })

    assert message["content"][0] == {"type": "text", "text": "Read this"}
    assert message["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,cG5n"},
    }
    assert message["content"][2] == {
        "type": "file",
        "file": {"filename": "a.pdf", "file_data": "data:application/pdf;base64,cGRm"},
    }


def test_create_provider_returns_openai_when_ai_provider_names_it(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    assert isinstance(create_provider(Settings.from_env()), OpenAIProvider)
