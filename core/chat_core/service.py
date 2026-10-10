import json
import threading
from collections.abc import Iterator

import httpx
from anthropic import Anthropic
from openrouter import OpenRouter

from .duckdb_store import DuckDBSessionStore
from .openrouter_http import CitationHttpClient
from .settings import Settings
from .store import SessionStore


class ProviderStreamError(Exception):
    pass


class ChatService:
    def __init__(
        self,
        store: SessionStore | DuckDBSessionStore,
        client: Anthropic | None = None,
        settings: Settings | None = None,
        tools_enabled: list[str] | None = None,
        openrouter_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.settings = settings
        self.tools_enabled = tools_enabled if tools_enabled else []
        self._openrouter_http = CitationHttpClient(transport=openrouter_transport)
        self._openrouter: OpenRouter | None = None
        self._openrouter_lock = threading.Lock()

    def stream_reply(self, session_id: str, prompt: str, model: str | None = None) -> Iterator[str]:
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
        model = (model or "").strip() or settings.model

        chunks: list[str] = []
        sources: list[dict] = []

        if settings.provider == "openrouter":
            deltas = self._openrouter_deltas(settings, model, conversation, sources)
        else:
            deltas = self._anthropic_deltas(settings, model, conversation, sources)

        for text in deltas:
            chunks.append(text)
            yield text

        self.store.add_message(
            session_id,
            "assistant",
            "".join(chunks),
            json.dumps(sources),
            model,
        )

    def _anthropic_deltas(
        self,
        settings: Settings,
        model: str,
        conversation: list[dict],
        sources: list[dict],
    ) -> Iterator[str]:
        params = {
            "model": model,
            "max_tokens": 2048,
            "messages": conversation,
            "stream": True
        }

        tools = [{"type": tool} for tool in self.tools_enabled]
        if len(tools) > 0:
            params["tools"] = tools

        response = self._anthropic_client(settings).messages.create(**params)

        for event in response:
            if event.type == "content_block_delta" and event.delta.type == "citations_delta":
                sources.append({
                    "title": event.delta.citation.title,
                    "url": event.delta.citation.url
                })
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield event.delta.text

    def _openrouter_deltas(
        self,
        settings: Settings,
        model: str,
        conversation: list[dict],
        sources: list[dict],
    ) -> Iterator[str]:
        params = {
            "model": model,
            "max_completion_tokens": 2048,
            "messages": conversation,
        }

        if "web_search" in self.tools_enabled:
            params["plugins"] = [{"id": "web"}]

        with (
            self._openrouter_http.collecting(sources),
            self._openrouter_client(settings).chat.send(stream=True, **params) as stream,
        ):
            for chunk in stream:
                if chunk.error is not None:
                    raise ProviderStreamError(chunk.error.message)

                for choice in chunk.choices:
                    if choice.delta.content:
                        yield choice.delta.content

    def _openrouter_client(self, settings: Settings) -> OpenRouter:
        with self._openrouter_lock:
            if self._openrouter is None:
                self._openrouter = OpenRouter(
                    api_key=settings.api_key,
                    client=self._openrouter_http,
                )

            return self._openrouter

    def _anthropic_client(self, settings: Settings) -> Anthropic:
        if self.client is not None:
            return self.client

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
