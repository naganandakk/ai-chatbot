from collections.abc import Iterator

from anthropic import Anthropic, APIError

from .base import (
    MAX_TOKENS,
    Citation,
    ProviderError,
    ProviderEvent,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
)


class AnthropicProvider:
    def __init__(self, api_key: str, client: Anthropic | None = None) -> None:
        self._client = client or Anthropic(api_key=api_key)

    def stream(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[str],
    ) -> Iterator[ProviderEvent]:
        params = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "messages": messages,
            "stream": True,
        }

        if tools:
            params["tools"] = [{"type": tool} for tool in tools]

        stop_reason = None
        wrote_text = False

        try:
            response = self._client.messages.create(**params)

            for event in response:
                if event.type == "message_delta":
                    stop_reason = event.delta.stop_reason
                if event.type == "content_block_delta" and event.delta.type == "citations_delta":
                    yield Citation(title=event.delta.citation.title, url=event.delta.citation.url)
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    wrote_text = True
                    yield TextDelta(event.delta.text)

            if stop_reason == "max_tokens":
                if not wrote_text:
                    raise TruncatedReplyError()
                yield ReplyTruncated()
        except APIError as error:
            raise ProviderError(str(error)) from error
