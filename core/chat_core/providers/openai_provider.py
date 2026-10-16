import base64
from collections.abc import Iterator

from openai import APIError, OpenAI

from ..settings import DEFAULT_MAX_TOKENS
from .base import (
    ModelInfo,
    ProviderError,
    ProviderEvent,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
    Usage,
)
from .pricing import openai_cost


class OpenAIProvider:
    def __init__(
        self,
        api_key: str,
        client: OpenAI | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._max_tokens = max_tokens

    def close(self) -> None:
        self._client.close()

    def stream(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[str],
    ) -> Iterator[ProviderEvent]:
        # Tool ids are not mapped yet, so every tool is ignored for this provider
        params = {
            "model": model,
            "max_completion_tokens": self._max_tokens,
            "messages": [_openai_message(message) for message in messages],
            "stream": True,
            # The final chunk carries usage only when this is set
            "stream_options": {"include_usage": True},
        }

        finish_reason = None
        wrote_text = False
        usage = None

        try:
            response = self._client.chat.completions.create(**params)

            for chunk in response:
                # Only the final chunk carries usage, and it has no choices
                if chunk.usage is not None:
                    usage = chunk.usage

                for choice in chunk.choices:
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                    if choice.delta.content:
                        wrote_text = True
                        yield TextDelta(choice.delta.content)

            if usage is not None:
                # Cached tokens are part of prompt_tokens, as they are for the other providers
                details = usage.prompt_tokens_details
                cache_read = (details.cached_tokens or 0) if details else 0
                yield Usage(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    cost_usd=openai_cost(
                        model,
                        input_tokens=usage.prompt_tokens,
                        cached_tokens=cache_read,
                        output_tokens=usage.completion_tokens,
                    ),
                    cache_read_tokens=cache_read,
                )

            if finish_reason == "length":
                if not wrote_text:
                    raise TruncatedReplyError()
                yield ReplyTruncated()
        except APIError as error:
            raise ProviderError(str(error)) from error

    def list_models(self) -> list[ModelInfo]:
        try:
            # Iterating the page fetches every page of results
            return [ModelInfo(id=model.id, name=model.id) for model in self._client.models.list()]
        except APIError as error:
            raise ProviderError(str(error)) from error


def _openai_message(message: dict) -> dict:
    if isinstance(message["content"], str):
        return message
    return {**message, "content": [_openai_block(block) for block in message["content"]]}


def _openai_block(block: dict) -> dict:
    # Files go in as data URLs inside Chat Completions content parts
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
