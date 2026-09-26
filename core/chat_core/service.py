from pathlib import Path
import os
from collections.abc import Iterator

from anthropic import Anthropic
from dotenv import load_dotenv

from .store import SessionStore

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class ChatService:
    def __init__(
        self,
        store: SessionStore,
        client: Anthropic | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.provider = self._provider()
        self.model = os.getenv("CLAUDE_MODEL", self._default_model())

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

        response = self._client().messages.create(
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

    def _client(self) -> Anthropic:
        if self.client is not None:
            return self.client

        if self.provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouter")

            return Anthropic(
                api_key=api_key,
                base_url="https://openrouter.ai/api",
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic")

        return Anthropic(api_key=api_key)

    @staticmethod
    def _provider() -> str:
        provider = os.getenv("AI_PROVIDER", "").lower()

        if provider in {"anthropic", "openrouter"}:
            return provider

        return "openrouter" if os.getenv("OPENROUTER_API_KEY") else "anthropic"

    def _default_model(self) -> str:
        if self.provider == "openrouter":
            return "anthropic/claude-haiku-4.5"

        return "claude-haiku-4-5"