import os
from collections.abc import Iterator

from anthropic import Anthropic

from .store import SessionStore


class ChatService:
    def __init__(
        self,
        store: SessionStore,
        client: Anthropic | None = None,
    ) -> None:
        self.store = store
        self.client = client or Anthropic()
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

    def stream_reply(self, session_id: str, prompt: str) -> Iterator[str]:
        message = prompt.strip()
        if not message:
            raise ValueError("Message cannot be empty")

        self.store.add_message(session_id, "user", message)
        session = self.store.get(session_id)

        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        conversation = [
            {"role": chat_message.role, "content": chat_message.content}
            for chat_message in session.messages
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=conversation,
            stream=True,
        )

        chunks: list[str] = []

        for event in response:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                chunks.append(event.delta.text)
                yield event.delta.text

        self.store.add_message(session_id, "assistant", "".join(chunks))