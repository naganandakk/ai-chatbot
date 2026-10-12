import json
import logging
import threading
import time
from collections.abc import Generator, Sequence
from dataclasses import asdict

from .attachments import (
    AttachmentLimits,
    UploadedFile,
    attachment_block,
    prepare_attachments,
)
from .models import ChatMessage, ChatSession
from .providers import (
    Citation,
    ModelInfo,
    ModelProvider,
    ProviderError,
    ReplyReset,
    ReplyTruncated,
    TextDelta,
    Usage,
    create_provider,
)
from .settings import Settings
from .store import SessionStore

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        store: SessionStore,
        provider: ModelProvider | None = None,
        settings: Settings | None = None,
        tools_enabled: list[str] | None = None,
        attachment_limits: AttachmentLimits | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.settings = settings
        self.tools_enabled = tools_enabled if tools_enabled else []
        self.attachment_limits = attachment_limits or AttachmentLimits()
        self._resolve_lock = threading.Lock()

    def stream_reply(
        self,
        session_id: str,
        prompt: str,
        model: str | None = None,
        files: Sequence[UploadedFile] = (),
    ) -> Generator[str | ReplyReset, None, ChatMessage]:
        # Yields text deltas, and a ReplyReset when earlier text is discarded. Returns the
        # saved assistant message once the reply ends. Files are optional, so a message can
        # be attachments only.
        message = prompt.strip()
        if not message and not files:
            raise ValueError("Message cannot be empty")

        session = self.store.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        attachments = prepare_attachments(
            files,
            self.attachment_limits,
            existing_bytes=_attachment_bytes(session),
        )
        self.store.add_message(session_id, "user", message, attachments=attachments)
        session = self.store.get(session_id)

        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        conversation = self._conversation(session)
        settings, provider = self._resolve()
        model = (model or "").strip() or settings.model

        chunks: list[str] = []
        sources: list[dict] = []
        truncated = False
        usage: Usage | None = None

        started = time.perf_counter()
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
            elif isinstance(event, Usage):
                # Kept across a ReplyReset, since tokens spent on narration were still billed
                usage = event

        duration_ms = round((time.perf_counter() - started) * 1000)

        return self.store.add_message(
            session_id,
            "assistant",
            "".join(chunks),
            json.dumps(sources),
            model,
            truncated,
            json.dumps(asdict(usage)) if usage else "",
            duration_ms,
        )

    def _conversation(self, session: ChatSession) -> list[dict]:
        conversation = []
        for chat_message in session.messages:
            if not chat_message.attachments:
                conversation.append({"role": chat_message.role, "content": chat_message.content})
                continue

            # Files come before the text, which suits how models read attached documents
            blocks = [
                attachment_block(self.store.get_attachment(attachment.id))
                for attachment in chat_message.attachments
            ]
            if chat_message.content:
                blocks.append({"type": "text", "text": chat_message.content})
            conversation.append({"role": chat_message.role, "content": blocks})

        return conversation

    def warm_up(self) -> None:
        # Fetches the model list once so reasoning requirements are known before the first
        # message. A failure is logged and the server still starts.
        try:
            _, provider = self._resolve()
            provider.list_models()
        except (RuntimeError, ProviderError) as error:
            logger.warning("Could not load the model list at startup: %s", error)

    def list_models(self) -> list[ModelInfo]:
        _, provider = self._resolve()
        return provider.list_models()

    def default_model(self) -> str:
        settings, _ = self._resolve()
        return settings.model

    def _resolve(self) -> tuple[Settings, ModelProvider]:
        # Settings and the provider are created on first use, so a missing API key
        # fails at the first message rather than at import time.
        with self._resolve_lock:
            if self.settings is None:
                self.settings = Settings.from_env()

            if self.provider is None:
                self.provider = create_provider(self.settings)

            return self.settings, self.provider


def _attachment_bytes(session: ChatSession) -> int:
    return sum(
        attachment.size
        for chat_message in session.messages
        for attachment in chat_message.attachments
    )
