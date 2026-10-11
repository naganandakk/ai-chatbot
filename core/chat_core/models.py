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
        return session