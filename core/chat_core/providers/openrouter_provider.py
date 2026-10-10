from collections.abc import Iterator

import httpx
from openrouter import OpenRouter
from openrouter.errors import OpenRouterError

from ..settings import DEFAULT_MAX_TOKENS
from .base import (
    Citation,
    ProviderError,
    ProviderEvent,
    ProviderStreamError,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
)
from .openrouter_http import CitationHttpClient


class OpenRouterProvider:
    def __init__(
        self,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._http = CitationHttpClient(transport=transport)
        self._client = OpenRouter(api_key=api_key, client=self._http)
        self._max_tokens = max_tokens

    def stream(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[str],
    ) -> Iterator[ProviderEvent]:
        params = {
            "model": model,
            "max_completion_tokens": self._max_tokens,
            "messages": messages,
            # Reasoning tokens count against max_completion_tokens, and on reasoning models
            # they can use the whole budget and leave no visible reply.
            "reasoning": {"effort": "none"},
        }

        if "web_search" in tools:
            params["plugins"] = [{"id": "web"}]

        # The citation tap appends into this list while the SDK reads the stream. It is
        # bound to this thread only, so concurrent replies keep separate citations.
        sources: list[dict] = []
        finish_reason = None
        wrote_text = False

        try:
            with (
                self._http.collecting(sources),
                self._client.chat.send(stream=True, **params) as stream,
            ):
                for chunk in stream:
                    if chunk.error is not None:
                        raise ProviderStreamError(chunk.error.message)

                    for choice in chunk.choices:
                        if choice.finish_reason:
                            finish_reason = choice.finish_reason
                        if choice.delta.content:
                            wrote_text = True
                            yield TextDelta(choice.delta.content)

            if finish_reason == "length":
                if not wrote_text:
                    raise TruncatedReplyError()
                yield ReplyTruncated()

            # Citation lines can arrive after the last text chunk, so emit them once the
            # stream has ended.
            for source in sources:
                yield Citation(title=source["title"], url=source["url"])
        except OpenRouterError as error:
            raise ProviderError(str(error)) from error
