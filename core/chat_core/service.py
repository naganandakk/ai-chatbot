from collections.abc import Iterator

from anthropic import Anthropic

from .settings import Settings
from .store import SessionStore
from .duckdb_store import DuckDBSessionStore


class ChatService:
    def __init__(
        self,
        store: SessionStore | DuckDBSessionStore,
        client: Anthropic | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.settings = settings

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
        settings = self._settings()

        response = self._client(settings).messages.create(
            model=settings.model,
            max_tokens=2048,
            messages=conversation,
            stream=True,
            tools=[{"type": "web_search"}],
        )

        chunks: list[str] = []
        sources: list[str] = []

        for event in response:
            if event.type == "content_block_delta" and event.delta.type == "citations_delta":
                sources.append(str({
                    "title": event.delta.citation.title,
                    "url": event.delta.citation.url
                }))
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                chunks.append(event.delta.text)
                yield event.delta.text

        self.store.add_message(session_id, "assistant", "".join(chunks), str(sources))

    def _client(self, settings: Settings) -> Anthropic:
        if self.client is not None:
            return self.client

        if settings.provider == "openrouter":
            return Anthropic(
                api_key=settings.api_key,
                base_url="https://openrouter.ai/api",
            )

        return Anthropic(api_key=settings.api_key)

    def _settings(self) -> Settings:
        if self.settings is not None:
            return self.settings

        if self.client is not None:
            return Settings(
                provider="anthropic",
                api_key="test-key",
                model="test-model",
            )

        return Settings.from_env()