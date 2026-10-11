import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)
    sources: str = ""
    model: str = ""
    truncated: bool = False
    # JSON of the reply's token counts and cost, empty when the provider reported none
    usage: str = ""
    # Milliseconds from sending the request to the end of the reply, None for older messages
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "sources": json.loads(self.sources.strip()) if self.sources.strip() else [],
            "model": self.model,
            "truncated": self.truncated,
            "usage": _usage_to_dict(self.usage),
            "durationMs": self.duration_ms,
            "createdAt": self.created_at,
        }


def _usage_to_dict(raw: str) -> dict[str, Any] | None:
    if not raw.strip():
        return None

    usage = json.loads(raw)
    return {
        "inputTokens": usage["input_tokens"],
        "outputTokens": usage["output_tokens"],
        "costUsd": usage["cost_usd"],
    }


@dataclass(frozen=True)
class UsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    # None when no reply in the session has a known cost
    cost_usd: float | None = None
    priced_messages: int = 0
    unpriced_messages: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "costUsd": self.cost_usd,
            "pricedMessages": self.priced_messages,
            "unpricedMessages": self.unpriced_messages,
        }


def summarize_usage(messages: list[ChatMessage]) -> UsageSummary:
    # Only replies carry usage. The cost is summed over the priced replies, and the unpriced
    # count tells the client the total is partial.
    input_tokens = output_tokens = priced = unpriced = 0
    cost_usd = 0.0

    for message in messages:
        if not message.usage.strip():
            continue

        usage = json.loads(message.usage)
        input_tokens += usage["input_tokens"]
        output_tokens += usage["output_tokens"]
        if usage["cost_usd"] is None:
            unpriced += 1
        else:
            priced += 1
            cost_usd += usage["cost_usd"]

    return UsageSummary(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd if priced else None,
        priced_messages=priced,
        unpriced_messages=unpriced,
    )


@dataclass
class ChatSession:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "New chat"
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self, include_messages: bool = True) -> dict:
        session = {
            "id": self.id,
            "title": self.title,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if include_messages:
            session["messages"] = [message.to_dict() for message in self.messages]
            session["usage"] = summarize_usage(self.messages).to_dict()
        return session