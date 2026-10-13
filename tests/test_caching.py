import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx

from core.chat_core.providers import AnthropicProvider, OpenRouterProvider, Usage, caching
from core.chat_core.providers.caching import CachePolicy, conversation_key

START = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
BIG = "x" * 12_000  # about 3000 tokens, above MIN_CACHE_TOKENS
SMALL = "hi"


def long_conversation(text: str = BIG) -> list[dict]:
    return [{"role": "user", "content": text}]


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def patch_clock(monkeypatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(caching, "_now", clock)
    return clock


def test_small_prompt_is_not_cached():
    policy = CachePolicy()

    assert policy.params_for(model="m", messages=long_conversation(SMALL)) == {}


def test_large_prompt_gets_a_five_minute_marker():
    policy = CachePolicy()

    params = policy.params_for(model="m", messages=long_conversation())

    assert params == {"cache_control": {"type": "ephemeral"}}


def test_slow_follow_up_gets_a_one_hour_marker(monkeypatch):
    clock = patch_clock(monkeypatch)
    policy = CachePolicy()
    messages = long_conversation()

    policy.params_for(model="m", messages=messages)
    clock.advance(minutes=6)
    params = policy.params_for(model="m", messages=messages)

    assert params == {"cache_control": {"type": "ephemeral", "ttl": "1h"}}


def test_quick_follow_up_keeps_the_five_minute_marker(monkeypatch):
    clock = patch_clock(monkeypatch)
    policy = CachePolicy()
    messages = long_conversation()

    policy.params_for(model="m", messages=messages)
    clock.advance(minutes=1)
    params = policy.params_for(model="m", messages=messages)

    assert params == {"cache_control": {"type": "ephemeral"}}


def test_two_turns_without_a_read_pause_caching_then_it_resumes(monkeypatch):
    clock = patch_clock(monkeypatch)
    policy = CachePolicy()
    messages = long_conversation()

    policy.params_for(model="m", messages=messages)
    policy.record(model="m", messages=messages, cache_write_tokens=3000, cache_read_tokens=0)  # seed
    policy.params_for(model="m", messages=messages)
    policy.record(model="m", messages=messages, cache_write_tokens=3000, cache_read_tokens=0)
    policy.params_for(model="m", messages=messages)
    policy.record(model="m", messages=messages, cache_write_tokens=3000, cache_read_tokens=0)

    assert policy.params_for(model="m", messages=messages) == {}

    # Caching resumes after the pause, with a 1 hour marker because the user has been away
    clock.advance(minutes=31)
    assert policy.params_for(model="m", messages=messages) == {
        "cache_control": {"type": "ephemeral", "ttl": "1h"}
    }


def test_a_cache_read_resets_the_miss_count(monkeypatch):
    patch_clock(monkeypatch)
    policy = CachePolicy()
    messages = long_conversation()

    policy.record(model="m", messages=messages, cache_write_tokens=3000, cache_read_tokens=0)
    policy.record(model="m", messages=messages, cache_write_tokens=3000, cache_read_tokens=0)
    policy.record(model="m", messages=messages, cache_write_tokens=0, cache_read_tokens=3000)
    policy.record(model="m", messages=messages, cache_write_tokens=3000, cache_read_tokens=0)

    assert policy.params_for(model="m", messages=messages) != {}


def test_models_that_do_not_apply_get_no_marker():
    policy = CachePolicy(applies_to=lambda model: model.startswith("anthropic/"))

    assert policy.params_for(model="openai/gpt", messages=long_conversation()) == {}
    assert policy.params_for(model="anthropic/claude", messages=long_conversation()) != {}


def test_conversation_key_is_stable_as_the_conversation_grows():
    first = long_conversation()
    later = first + [
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "follow up"},
    ]

    assert conversation_key("m", first) == conversation_key("m", later)
    assert conversation_key("m", first) != conversation_key("other", first)


def test_conversation_state_is_bounded(monkeypatch):
    monkeypatch.setattr(caching, "MAX_CONVERSATIONS", 2)
    policy = CachePolicy()

    for index in range(5):
        policy.params_for(model="m", messages=long_conversation(f"{index}" + BIG))

    assert len(policy._conversations) == 2


def test_anthropic_request_carries_cache_marker_only_for_large_history():
    class Messages:
        def __init__(self) -> None:
            self.requests: list[dict] = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            return []

    messages = Messages()
    provider = AnthropicProvider(api_key="k", client=SimpleNamespace(messages=messages))

    list(provider.stream(model="claude-sonnet-5-5", messages=long_conversation(), tools=[]))
    list(provider.stream(model="claude-sonnet-5-5", messages=long_conversation(SMALL), tools=[]))

    assert messages.requests[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in messages.requests[1]


def test_openrouter_marks_only_anthropic_models():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        payload = {
            "id": "gen-1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "x",
            "choices": [{"index": 0, "delta": {"content": "ok", "role": "assistant"},
                         "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 3000,
                "completion_tokens": 2,
                "total_tokens": 3002,
                "prompt_tokens_details": {"cached_tokens": 2500, "cache_write_tokens": 0},
            },
        }
        body = f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n".encode()
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(body),
        )

    provider = OpenRouterProvider(api_key="k", transport=httpx.MockTransport(handler))

    list(provider.stream(model="anthropic/claude-haiku-4.5", messages=long_conversation(), tools=[]))
    list(provider.stream(model="openai/gpt-5", messages=long_conversation(), tools=[]))

    assert bodies[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in bodies[1]


def test_openrouter_reports_cache_counts_in_usage_event():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "id": "gen-1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "x",
            "choices": [{"index": 0, "delta": {"content": "ok", "role": "assistant"},
                         "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 3000,
                "completion_tokens": 2,
                "total_tokens": 3002,
                "prompt_tokens_details": {"cached_tokens": 2500, "cache_write_tokens": 100},
            },
        }
        body = f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n".encode()
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=httpx.ByteStream(body),
        )

    provider = OpenRouterProvider(api_key="k", transport=httpx.MockTransport(handler))

    events = list(provider.stream(model="anthropic/claude-haiku-4.5", messages=long_conversation(), tools=[]))
    usage = next(event for event in events if isinstance(event, Usage))

    assert usage.input_tokens == 3000
    assert usage.cache_read_tokens == 2500
    assert usage.cache_write_tokens == 100
