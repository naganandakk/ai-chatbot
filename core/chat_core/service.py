import json
import logging
import os
import threading
import time
from collections.abc import Generator, Sequence
from dataclasses import asdict

from .accounts import AccountStore
from .attachments import (
    AttachmentLimits,
    UploadedFile,
    attachment_block,
    prepare_attachments,
)
from .key_vault import KeyVault, KeyVaultError
from .models import ChatMessage, ChatSession
from .provider_pool import ProviderPool
from .providers import (
    PROVIDERS,
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
from .settings import DEFAULT_MAX_TOKENS, Settings, default_model, positive_int_from_env
from .store import SessionStore

logger = logging.getLogger(__name__)


class ApiKeyRequired(ValueError):
    """The caller has no usable API key saved for the provider they asked for."""


class ChatService:
    # Two ways to get a provider. With `accounts` and `key_vault` (the web app), each caller
    # replies with their own saved key. Without them (the CLI, and tests that inject a
    # provider), one key comes from the environment or the injected provider.
    def __init__(
        self,
        store: SessionStore,
        provider: ModelProvider | None = None,
        settings: Settings | None = None,
        tools_enabled: list[str] | None = None,
        attachment_limits: AttachmentLimits | None = None,
        accounts: AccountStore | None = None,
        key_vault: KeyVault | None = None,
        provider_pool: ProviderPool | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.settings = settings
        self.tools_enabled = tools_enabled if tools_enabled else []
        self.attachment_limits = attachment_limits or AttachmentLimits()
        self.accounts = accounts
        self.key_vault = key_vault
        self.provider_pool = provider_pool or ProviderPool()
        self.max_tokens = max_tokens or positive_int_from_env("MAX_TOKENS", DEFAULT_MAX_TOKENS)
        self._resolve_lock = threading.Lock()

    def stream_reply(
        self,
        user_id: str,
        session_id: str,
        prompt: str,
        model: str | None = None,
        files: Sequence[UploadedFile] = (),
        provider_name: str | None = None,
    ) -> Generator[str | ReplyReset, None, ChatMessage]:
        # Yields text deltas, and a ReplyReset when earlier text is discarded. Returns the
        # saved assistant message once the reply ends. Files are optional, so a message can
        # be attachments only.
        message = prompt.strip()
        if not message and not files:
            raise ValueError("Message cannot be empty")

        # Resolved before anything is saved, so a missing key leaves no unanswered message
        default_model_name, provider = self._resolve(user_id, provider_name)

        session = self.store.get(user_id, session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        attachments = prepare_attachments(
            files,
            self.attachment_limits,
            existing_bytes=_attachment_bytes(session),
        )
        self.store.add_message(user_id, session_id, "user", message, attachments=attachments)
        session = self.store.get(user_id, session_id)

        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        conversation = self._conversation(user_id, session)
        model = (model or "").strip() or default_model_name

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
            user_id,
            session_id,
            "assistant",
            "".join(chunks),
            json.dumps(sources),
            model,
            truncated,
            json.dumps(asdict(usage)) if usage else "",
            duration_ms,
        )

    def _conversation(self, user_id: str, session: ChatSession) -> list[dict]:
        conversation = []
        for chat_message in session.messages:
            if not chat_message.attachments:
                conversation.append({"role": chat_message.role, "content": chat_message.content})
                continue

            # Files come before the text, which suits how models read attached documents
            blocks = [
                attachment_block(self.store.get_attachment(user_id, attachment.id))
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
            _, provider = self._resolve(None)
            provider.list_models()
        except (RuntimeError, ProviderError) as error:
            logger.warning("Could not load the model list at startup: %s", error)

    def list_models(self, user_id: str | None = None, provider_name: str | None = None) -> list[ModelInfo]:
        _, provider = self._resolve(user_id, provider_name)
        return provider.list_models()

    def default_model(self, user_id: str | None = None) -> str:
        default, _ = self._resolve(user_id)
        return default

    def _resolve(self, user_id: str | None, provider_name: str | None = None) -> tuple[str, ModelProvider]:
        # Returns the default model name and the provider to call
        if self.provider is not None:
            return self._server_settings().model, self.provider

        if self.accounts is None:
            settings, provider = self._server_resolve()
            return settings.model, provider

        name = self.provider_name_for(user_id, provider_name)
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {name}")

        api_key = self._user_api_key(user_id, name)
        return default_model(name), self.provider_pool.get(name, api_key, self.max_tokens)

    def provider_name_for(self, user_id: str | None, provider_name: str | None = None) -> str:
        # The provider named in the request, else the one the user chose, else the default
        requested = (provider_name or "").strip().lower()
        if requested:
            return requested

        chosen = self.accounts.get_active_provider(user_id) if self.accounts and user_id else None
        return chosen or _default_provider_name()

    def _user_api_key(self, user_id: str, provider_name: str) -> str:
        record = self.accounts.get_api_key(user_id, provider_name)
        if record is None:
            raise ApiKeyRequired(f"Add an API key for {provider_name} in settings to start chatting.")

        try:
            return self.key_vault.decrypt(user_id, provider_name, record.sealed)
        except KeyVaultError:
            raise ApiKeyRequired(
                f"Your saved {provider_name} API key could not be read. Add it again in settings."
            ) from None

    def _server_settings(self) -> Settings:
        with self._resolve_lock:
            if self.settings is None:
                self.settings = Settings.from_env()
            return self.settings

    def _server_resolve(self) -> tuple[Settings, ModelProvider]:
        # Settings and the provider are created on first use, so a missing API key
        # fails at the first message rather than at import time.
        with self._resolve_lock:
            if self.settings is None:
                self.settings = Settings.from_env()

            if self.provider is None:
                self.provider = create_provider(self.settings)

            return self.settings, self.provider


def _default_provider_name() -> str:
    return os.getenv("AI_PROVIDER", "").strip().lower() or "anthropic"


def _attachment_bytes(session: ChatSession) -> int:
    return sum(
        attachment.size
        for chat_message in session.messages
        for attachment in chat_message.attachments
    )
