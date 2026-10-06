from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)
    sources: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "sources": json.loads(self.sources.strip()) if self.sources.strip() else [],
            "createdAt": self.created_at,
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