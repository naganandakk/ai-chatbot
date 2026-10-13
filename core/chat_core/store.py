from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import replace
from uuid import uuid4

from .accounts import AccountStore, ApiKeyRecord, AuditEvent, RefreshToken, User
from .key_vault import EncryptedKey
from .models import Attachment, ChatMessage, ChatSession, utc_now


class SessionStore(ABC):
    """Persistence contract for chat sessions.

    Every method takes the owning `user_id` first. A session or attachment that belongs to
    another user is treated as missing, so it raises `KeyError` exactly like an unknown ID.
    `list` returns summaries (no messages), newest first. Every method that takes a
    session ID or attachment ID raises `KeyError` when it does not exist. `get` returns
    attachment metadata only; `get_attachment` returns the bytes. Implementations must
    be safe to call from several threads at once.
    """

    @abstractmethod
    def create(self, user_id: str) -> ChatSession:
        ...

    @abstractmethod
    def get(self, user_id: str, session_id: str) -> ChatSession | None:
        ...

    @abstractmethod
    def list(self, user_id: str) -> list[ChatSession]:
        ...

    @abstractmethod
    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        sources: str = "",
        model: str = "",
        truncated: bool = False,
        usage: str = "",
        duration_ms: int | None = None,
        attachments: Sequence[Attachment] = (),
    ) -> ChatMessage:
        ...

    @abstractmethod
    def get_attachment(self, user_id: str, attachment_id: str) -> Attachment:
        ...

    @abstractmethod
    def clear(self, user_id: str, session_id: str) -> ChatSession:
        ...

    @abstractmethod
    def delete(self, user_id: str, session_id: str) -> None:
        ...

    @abstractmethod
    def update(self, user_id: str, session_id: str, title: str) -> ChatSession:
        ...

    def close(self) -> None:
        # Stores without external resources need no cleanup.
        return None

    def _require(self, user_id: str, session_id: str) -> ChatSession:
        session = self.get(user_id, session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    @staticmethod
    def _title_for(content: str) -> str:
        normalized = content.strip().replace("\n", " ")
        return normalized[:48] or "New chat"


class InMemorySessionStore(SessionStore, AccountStore):
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._owners: dict[str, str] = {}
        self._users: dict[str, User] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}
        self._api_keys: dict[tuple[str, str], ApiKeyRecord] = {}
        self._active_providers: dict[str, str | None] = {}
        self._audit_events: list[AuditEvent] = []

    def create(self, user_id: str) -> ChatSession:
        session = ChatSession()
        self._sessions[session.id] = session
        self._owners[session.id] = user_id
        return session

    def get(self, user_id: str, session_id: str) -> ChatSession | None:
        session = self._owned(user_id, session_id)
        if session is None:
            return None

        # Metadata only, as the other stores return it. Bytes come from get_attachment.
        return replace(
            session,
            messages=[
                replace(
                    message,
                    attachments=[replace(a, data=b"") for a in message.attachments],
                )
                for message in session.messages
            ],
        )

    def _owned(self, user_id: str, session_id: str) -> ChatSession | None:
        # Returns the stored session itself (not a copy), so callers must not mutate it
        # unless they are one of the write methods below.
        if self._owners.get(session_id) != user_id:
            return None
        return self._sessions.get(session_id)

    def _require(self, user_id: str, session_id: str) -> ChatSession:
        # Mutations work on the stored session, not the copy that get returns
        session = self._owned(user_id, session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def list(self, user_id: str) -> list[ChatSession]:
        sessions = sorted(
            (
                session
                for session_id, session in self._sessions.items()
                if self._owners.get(session_id) == user_id
            ),
            key=lambda session: session.created_at,
            reverse=True,
        )
        return [
            ChatSession(
                id=session.id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        sources: str = "",
        model: str = "",
        truncated: bool = False,
        usage: str = "",
        duration_ms: int | None = None,
        attachments: Sequence[Attachment] = (),
    ) -> ChatMessage:
        session = self._require(user_id, session_id)
        message = ChatMessage(
            role=role,
            content=content,
            sources=sources,
            model=model,
            truncated=truncated,
            usage=usage,
            duration_ms=duration_ms,
            attachments=list(attachments),
        )
        session.messages.append(message)

        if role == "user" and session.title == "New chat":
            session.title = self._title_for(content)

        session.updated_at = utc_now()
        return message

    def get_attachment(self, user_id: str, attachment_id: str) -> Attachment:
        for session_id, session in self._sessions.items():
            if self._owners.get(session_id) != user_id:
                continue
            for message in session.messages:
                for attachment in message.attachments:
                    if attachment.id == attachment_id:
                        return attachment
        raise KeyError(f"Attachment not found: {attachment_id}")

    def clear(self, user_id: str, session_id: str) -> ChatSession:
        session = self._require(user_id, session_id)
        session.messages.clear()
        session.title = "New chat"
        session.updated_at = utc_now()
        return session

    def delete(self, user_id: str, session_id: str) -> None:
        self._require(user_id, session_id)
        del self._sessions[session_id]
        del self._owners[session_id]

    def update(self, user_id: str, session_id: str, title: str) -> ChatSession:
        session = self._require(user_id, session_id)
        session.title = title
        session.updated_at = utc_now()
        return session

    def upsert_user(self, google_sub: str, email: str, name: str, picture: str) -> User:
        existing = next((user for user in self._users.values() if user.google_sub == google_sub), None)
        user_id = existing.id if existing else str(uuid4())
        user = User(id=user_id, google_sub=google_sub, email=email, name=name, picture=picture)
        self._users[user_id] = user
        return user

    def get_user(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def count_users(self) -> int:
        return len(self._users)

    def get_active_provider(self, user_id: str) -> str | None:
        return self._active_providers.get(user_id)

    def set_active_provider(self, user_id: str, provider: str | None) -> None:
        self._active_providers[user_id] = provider

    def claim_unowned_sessions(self, user_id: str) -> None:
        for session_id in self._sessions:
            self._owners.setdefault(session_id, user_id)

    def save_refresh_token(self, token_hash: str, user_id: str, expires_at: str) -> None:
        self._refresh_tokens[token_hash] = RefreshToken(
            user_id=user_id,
            expires_at=expires_at,
            revoked=False,
        )

    def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        return self._refresh_tokens.get(token_hash)

    def revoke_refresh_token(self, token_hash: str) -> None:
        token = self._refresh_tokens.get(token_hash)
        if token:
            self._refresh_tokens[token_hash] = replace(token, revoked=True)

    def revoke_user_refresh_tokens(self, user_id: str) -> None:
        for token_hash, token in self._refresh_tokens.items():
            if token.user_id == user_id:
                self._refresh_tokens[token_hash] = replace(token, revoked=True)

    def save_api_key(self, user_id: str, provider: str, sealed: EncryptedKey, last4: str) -> None:
        self._api_keys[(user_id, provider)] = ApiKeyRecord(
            provider=provider,
            last4=last4,
            updated_at=utc_now(),
            sealed=sealed,
        )

    def get_api_key(self, user_id: str, provider: str) -> ApiKeyRecord | None:
        return self._api_keys.get((user_id, provider))

    def list_api_keys(self, user_id: str) -> list[ApiKeyRecord]:
        return sorted(
            (record for (owner, _), record in self._api_keys.items() if owner == user_id),
            key=lambda record: record.provider,
        )

    def list_all_api_keys(self) -> list[tuple[str, ApiKeyRecord]]:
        return [(user_id, record) for (user_id, _), record in self._api_keys.items()]

    def replace_api_key_seal(
        self, user_id: str, provider: str, expected: EncryptedKey, sealed: EncryptedKey
    ) -> bool:
        record = self._api_keys.get((user_id, provider))
        if record is None or record.sealed.nonce != expected.nonce:
            return False

        self._api_keys[(user_id, provider)] = replace(record, sealed=sealed)
        return True

    def delete_api_key(self, user_id: str, provider: str) -> None:
        self._api_keys.pop((user_id, provider), None)

    def record_audit_event(self, user_id: str, action: str, provider: str) -> None:
        self._audit_events.append(
            AuditEvent(
                id=str(uuid4()),
                user_id=user_id,
                action=action,
                provider=provider,
                created_at=utc_now(),
            )
        )

    def list_audit_events(self, user_id: str) -> list[AuditEvent]:
        return [event for event in self._audit_events if event.user_id == user_id]
