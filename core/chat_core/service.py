import json
import threading
from collections.abc import Generator

from .models import ChatMessage
from .providers import (
    Citation,
    ModelProvider,
    ReplyReset,
    ReplyTruncated,
    TextDelta,
    create_provider,
)
from .settings import Settings
from .store import SessionStore


class ChatService:
    def __init__(
        self,
        store: SessionStore,
        provider: ModelProvider | None = None,
        settings: Settings | None = None,
        tools_enabled: list[str] | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.settings = settings
        self.tools_enabled = tools_enabled if tools_enabled else []
        self._resolve_lock = threading.Lock()

    def stream_reply(
        self, session_id: str, prompt: str, model: str | None = None
    ) -> Generator[str | ReplyReset, None, ChatMessage]:
        # Yields text deltas, and a ReplyReset when earlier text is discarded. Returns the
        # saved assistant message once the reply ends.
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
        settings, provider = self._resolve()
        model = (model or "").strip() or settings.model

        chunks: list[str] = []
        sources: list[dict] = []
        truncated = False

        for event in provider.stream(
            model=model,
            messages=conversation,
            tools=self.tools_enabled,
        ):
            if isinstance(event, TextDelta):
                chunks.append(event.text)
                yield event.text
            elif isinstance(event, Citation):
                sources.append({"title": event.title, "url": event.url})
            elif isinstance(event, ReplyReset):
                # The text and sources so far were narration before a web search
                chunks.clear()
                sources.clear()
                yield event
            elif isinstance(event, ReplyTruncated):
                truncated = True

        return self.store.add_message(
            session_id,
            "assistant",
            "".join(chunks),
            json.dumps(sources),
            model,
            truncated,
        )

    def _resolve(self) -> tuple[Settings, ModelProvider]:
        # Settings and the provider are created on first use, so a missing API key
        # fails at the first message rather than at import time.
        with self._resolve_lock:
            if self.settings is None:
                self.settings = Settings.from_env()

            if self.provider is None:
                self.provider = create_provider(self.settings)

            return self.settings, self.provider
