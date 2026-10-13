import base64
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
    Usage,
)
from .openrouter_http import CitationHttpClient

WEB_SEARCH_INSTRUCTION = (
    "Web search is on. Do not say that you are going to search, look something up, or check "
    "recent data. Start directly with the answer, using what you found."
)
# Reasoning tokens count against max_completion_tokens, so replies turn it off by default.
# Some models always reason and reject "none", so they fall back to the lowest effort.
REASONING_OFF = {"effort": "none"}
REASONING_MANDATORY_ERROR = "Reasoning is mandatory"
# Fallback for models whose requirement is not in the model list yet. Matched by substring so
# "~anthropic/claude-sonnet-latest" also matches.
REASONING_MANDATORY_MODELS = ("claude-sonnet",)
# Lowest effort for each model that rejects "none", from the model list's reasoning metadata.
# Shared by every provider instance, since the requirement belongs to the model, not the key.
_MANDATORY_REASONING_EFFORTS: dict[str, str] = {}


def _record_reasoning_requirement(model) -> None:
    reasoning = getattr(model, "reasoning", None)
    if reasoning is None or not reasoning.mandatory:
        _MANDATORY_REASONING_EFFORTS.pop(model.id, None)
        return

    # supported_efforts is highest first, so the last entry is the lowest allowed effort
    efforts = reasoning.supported_efforts or []
    _MANDATORY_REASONING_EFFORTS[model.id] = efforts[-1] if efforts and efforts[-1] else "low"


class OpenRouterProvider:
    def __init__(
        self,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._http = CitationHttpClient(transport=transport)
        self._api_key = api_key
        self._client = OpenRouter(api_key=api_key, client=self._http)
        self._max_tokens = max_tokens
        # Models that rejected effort "none". Remembered so later replies skip that request.
        self._reasoning_required: set[str] = set()

    def close(self) -> None:
        self._http.close()

    def _requires_reasoning(self, model: str) -> bool:
        return (
            model in self._reasoning_required
            or model in _MANDATORY_REASONING_EFFORTS
            or any(marker in model for marker in REASONING_MANDATORY_MODELS)
        )

    def _send(self, model: str, params: dict):
        minimum = {"effort": _MANDATORY_REASONING_EFFORTS.get(model, "low")}
        if self._requires_reasoning(model):
            return self._client.chat.send(stream=True, reasoning=minimum, **params)

        try:
            return self._client.chat.send(stream=True, reasoning=REASONING_OFF, **params)
        except OpenRouterError as error:
            if REASONING_MANDATORY_ERROR not in str(error):
                raise

            self._reasoning_required.add(model)
            return self._client.chat.send(stream=True, reasoning=minimum, **params)

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
            "messages": [_openrouter_message(message) for message in messages],
        }

        if "web_search" in tools:
            params["plugins"] = [{"id": "web"}]
            # The web plugin searches on the server and sends no event when it starts, so the
            # provider cannot cut narration out of the stream. The instruction is the only control.
            params["messages"] = [
                {"role": "system", "content": WEB_SEARCH_INSTRUCTION},
                *params["messages"],
            ]

        # The citation tap appends into this list while the SDK reads the stream. It is
        # bound to this thread only, so concurrent replies keep separate citations.
        sources: list[dict] = []
        finish_reason = None
        wrote_text = False
        usage = None

        try:
            with (
                self._http.collecting(sources),
                self._send(model, params) as stream,
            ):
                for chunk in stream:
                    if chunk.error is not None:
                        raise ProviderStreamError(chunk.error.message)

                    # Only the final chunk carries usage
                    if chunk.usage is not None:
                        usage = chunk.usage

                    for choice in chunk.choices:
                        if choice.finish_reason:
                            finish_reason = choice.finish_reason
                        if choice.delta.content:
                            wrote_text = True
                            yield TextDelta(choice.delta.content)

            if usage is not None:
                # The cost is missing from the response for some models, so it stays None then
                cost = usage.cost if isinstance(usage.cost, (int, float)) else None
                yield Usage(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    cost_usd=cost,
                )

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
        # /models/user applies the account's provider preferences and privacy settings,
        # so only models the account can actually use are returned.
        try:
            response = self._client.models.list_for_user(security={"bearer": self._api_key})
        except OpenRouterError as error:
            raise ProviderError(str(error)) from error

        if response is None:
            return []

        models = response.result.data
        for model in models:
            _record_reasoning_requirement(model)

        # Batch variants ("<model>:batch") are for the batch API, not streamed chat replies
        return [
            ModelInfo(id=model.id, name=model.name)
            for model in models
            if not model.id.endswith(":batch")
        ]


def _openrouter_message(message: dict) -> dict:
    if isinstance(message["content"], str):
        return message
    return {**message, "content": [_openrouter_block(block) for block in message["content"]]}


def _openrouter_block(block: dict) -> dict:
    # OpenRouter takes files as data URLs inside OpenAI-style content parts
    if block["type"] == "image":
        return {"type": "image_url", "image_url": {"url": _data_url(block)}}
    if block["type"] == "document":
        return {
            "type": "file",
            "file": {"filename": block["filename"], "file_data": _data_url(block)},
        }
    return block


def _data_url(block: dict) -> str:
    encoded = base64.b64encode(block["data"]).decode("ascii")
    return f"data:{block['media_type']};base64,{encoded}"
