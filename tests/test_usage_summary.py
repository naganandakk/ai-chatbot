import json

from core.chat_core.models import ChatMessage, ChatSession, summarize_usage


def reply(input_tokens: int, output_tokens: int, cost_usd: float | None) -> ChatMessage:
    usage = json.dumps({
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    })
    return ChatMessage("assistant", "Hi", usage=usage)


def test_session_total_sums_replies_and_ignores_messages_without_usage():
    messages = [
        ChatMessage("user", "Hello"),
        reply(100, 20, 0.5),
        ChatMessage("user", "Again"),
        reply(300, 40, 1.25),
    ]

    summary = summarize_usage(messages).to_dict()

    assert summary == {
        "inputTokens": 400,
        "outputTokens": 60,
        "costUsd": 1.75,
        "pricedMessages": 2,
        "unpricedMessages": 0,
    }


def test_unpriced_replies_are_counted_and_left_out_of_the_cost():
    messages = [reply(100, 20, 0.5), reply(300, 40, None)]

    summary = summarize_usage(messages)

    assert summary.cost_usd == 0.5
    assert summary.priced_messages == 1
    assert summary.unpriced_messages == 1
    assert summary.input_tokens == 400


def test_cost_is_none_when_no_reply_has_a_price():
    summary = summarize_usage([reply(100, 20, None)])

    assert summary.to_dict()["costUsd"] is None
    assert summary.unpriced_messages == 1


def test_empty_session_has_zero_totals():
    assert summarize_usage([]).to_dict() == {
        "inputTokens": 0,
        "outputTokens": 0,
        "costUsd": None,
        "pricedMessages": 0,
        "unpricedMessages": 0,
    }


def test_session_dict_includes_usage_only_with_messages():
    session = ChatSession(messages=[reply(100, 20, 0.5)])

    assert session.to_dict()["usage"]["costUsd"] == 0.5
    assert "usage" not in session.to_dict(include_messages=False)
