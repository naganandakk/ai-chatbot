import base64
from collections.abc import Iterator

from anthropic import Anthropic, APIError

from ..settings import DEFAULT_MAX_TOKENS
from .base import (
    Citation,
    ModelInfo,
    ProviderError,
    ProviderEvent,
    ReplyReset,
    ReplyTruncated,
    TextDelta,
    TruncatedReplyError,
    Usage,
)
from .pricing import anthropic_cost

ANTHROPIC_API_URL = "https://api.anthropic.com"


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        client: Anthropic | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        # Pinned rather than read from ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN, so a stray
        # environment variable cannot send the user's key to another host
        self._client = client or Anthropic(
            api_key=api_key,
            base_url=ANTHROPIC_API_URL,
            auth_token=None,
        )
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
        params = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": [_anthropic_message(message) for message in messages],
            "stream": True,
        }

        if tools:
            params["tools"] = [{"type": tool} for tool in tools]

        stop_reason = None
        wrote_text = False
        input_tokens = cache_write_tokens = cache_read_tokens = 0
        output_tokens = web_searches = 0

        try:
            response = self._client.messages.create(**params)

            for event in response:
                if event.type == "message_start":
                    usage = event.message.usage
                    input_tokens = usage.input_tokens or 0
                    cache_write_tokens = usage.cache_creation_input_tokens or 0
                    cache_read_tokens = usage.cache_read_input_tokens or 0
                if event.type == "message_delta":
                    stop_reason = event.delta.stop_reason
                    # The output count in message_delta is a running total, so the last one wins
                    output_tokens = event.usage.output_tokens or 0
                    if event.usage.server_tool_use:
                        web_searches = event.usage.server_tool_use.web_search_requests or 0
                # Text written before a server tool call is the model narrating its search
                if (
                    event.type == "content_block_start"
                    and event.content_block.type == "server_tool_use"
                    and wrote_text
                ):
                    wrote_text = False
                    yield ReplyReset()
                if event.type == "content_block_delta" and event.delta.type == "citations_delta":
                    yield Citation(title=event.delta.citation.title, url=event.delta.citation.url)
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    wrote_text = True
                    yield TextDelta(event.delta.text)

            # Cache reads and writes are input tokens too, so they count toward the total
            yield Usage(
                input_tokens=input_tokens + cache_write_tokens + cache_read_tokens,
                output_tokens=output_tokens,
                cost_usd=anthropic_cost(
                    model,
                    input_tokens=input_tokens,
                    cache_write_tokens=cache_write_tokens,
                    cache_read_tokens=cache_read_tokens,
                    output_tokens=output_tokens,
                    web_searches=web_searches,
                ),
            )

            if stop_reason == "max_tokens":
                if not wrote_text:
                    raise TruncatedReplyError()
                yield ReplyTruncated()
        except APIError as error:
            raise ProviderError(str(error)) from error

    def list_models(self) -> list[ModelInfo]:
        try:
            # Iterating the page fetches every page of results
            return [
                ModelInfo(id=model.id, name=model.display_name)
                for model in self._client.models.list()
            ]
        except APIError as error:
            raise ProviderError(str(error)) from error


def _anthropic_message(message: dict) -> dict:
    if isinstance(message["content"], str):
        return message
    return {**message, "content": [_anthropic_block(block) for block in message["content"]]}


def _anthropic_block(block: dict) -> dict:
    if block["type"] in ("image", "document"):
        return {
            "type": block["type"],
            "source": {
                "type": "base64",
                "media_type": block["media_type"],
                "data": base64.b64encode(block["data"]).decode("ascii"),
            },
        }
    return block
