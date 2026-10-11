from collections.abc import Iterator

import httpx
from openrouter import OpenRouter
from openrouter.errors import OpenRouterError

from ..settings import DEFAULT_MAX_TOKENS
from .base import (
    Citation,
    ModelInfo,
    ProviderError,
    ProviderEvent,
    ProviderStreamError,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
)
from .openrouter_http import CitationHttpClient

WEB_SEARCH_INSTRUCTION = (
    "Web search is on. Do not say that you are going to search, look something up, or check "
    "recent data. Start directly with the answer, using what you found."
)
# Reasoning tokens count against max_completion_tokens, so replies turn it off by default.
# Some models always reason and reject "none", so they fall back to the lowest effort.
REASONING_OFF = {"effort": "none"}
REASONING_MINIMUM = {"effort": "low"}
REASONING_MANDATORY_ERROR = "Reasoning is mandatory"


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
        # Models that rejected effort "none". Remembered so later replies skip that request.
        self._reasoning_required: set[str] = set()

    def _send(self, model: str, params: dict):
        if model in self._reasoning_required:
            return self._client.chat.send(stream=True, reasoning=REASONING_MINIMUM, **params)

        try:
            return self._client.chat.send(stream=True, reasoning=REASONING_OFF, **params)
        except OpenRouterError as error:
            if REASONING_MANDATORY_ERROR not in str(error):
                raise

            self._reasoning_required.add(model)
            return self._client.chat.send(stream=True, reasoning=REASONING_MINIMUM, **params)

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
        }

        if "web_search" in tools:
            params["plugins"] = [{"id": "web"}]
            # The web plugin searches on the server and sends no event when it starts, so the
            # provider cannot cut narration out of the stream. The instruction is the only control.
            params["messages"] = [{"role": "system", "content": WEB_SEARCH_INSTRUCTION}, *messages]

        # The citation tap appends into this list while the SDK reads the stream. It is
        # bound to this thread only, so concurrent replies keep separate citations.
        sources: list[dict] = []
        finish_reason = None
        wrote_text = False

        try:
            with (
                self._http.collecting(sources),
                self._send(model, params) as stream,
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

    def list_models(self) -> list[ModelInfo]:
        try:
            response = self._client.models.list()
        except OpenRouterError as error:
            raise ProviderError(str(error)) from error

        return [ModelInfo(id=model.id, name=model.name) for model in response.result.data]
