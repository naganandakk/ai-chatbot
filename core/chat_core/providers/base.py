from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """A provider request failed. Raised by every provider, whatever its SDK."""


class ProviderStreamError(ProviderError):
    """The provider reported an error in the middle of a stream."""


class TruncatedReplyError(ProviderError):
    """The reply hit the token limit before any visible text was written."""

    def __init__(self) -> None:
        super().__init__(
            "The model used its token limit before writing a reply. Try a shorter question."
        )


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Citation:
    title: str
    url: str


@dataclass(frozen=True)
class ReplyTruncated:
    """Sent once, after the text, when the reply stopped at the token limit."""


@dataclass(frozen=True)
class ReplyReset:
    """Sent when the text so far was narration before a tool call. The reply starts over."""


ProviderEvent = TextDelta | Citation | ReplyTruncated | ReplyReset


class ModelProvider(Protocol):
    """Streams one model reply as normalized events.

    `messages` is the full conversation as `{"role", "content"}` dicts. `tools` holds
    tool names from `TOOLS_ENABLED`; each provider maps the names it understands and
    ignores the rest. Implementations must be safe to call from several threads at once.
    """

    def stream(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[str],
    ) -> Iterator[ProviderEvent]:
        ...
