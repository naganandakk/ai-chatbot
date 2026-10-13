from __future__ import annotations

import threading
from collections.abc import Sequence
from functools import wraps
from pathlib import Path
from uuid import uuid4

import duckdb

from .accounts import AccountStore, ApiKeyRecord, AuditEvent, RefreshToken, User
from .key_vault import EncryptedKey
from .models import Attachment, ChatMessage, ChatSession, attachments_by_message, utc_now
from .store import SessionStore


def _serialized(method):
    # One connection is shared by every request thread, and DuckDB connections are not
    # thread-safe. Hold the store lock so concurrent requests never interleave queries.
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class DuckDBSessionStore(SessionStore, AccountStore):
    def __init__(self, database_path: str) -> None:
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self.connection = duckdb.connect(database_path)
        self._initialize_schema()

    @_serialized
    def create(self, user_id: str) -> ChatSession:
        session = ChatSession()

        self.connection.execute(
            """
            INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                session.id,
                user_id,
                session.title,
                session.created_at,
                session.updated_at,
            ],
        )

        return session

    @_serialized
    def get(self, user_id: str, session_id: str) -> ChatSession | None:
        row = self.connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = ? AND user_id = ?
            """,
            [session_id, user_id],
        ).fetchone()

        if row is None:
            return None

        messages = self._load_messages(session_id)

        return ChatSession(
            id=row[0],
            title=row[1],
            messages=messages,
            created_at=row[2],
            updated_at=row[3],
        )

    @_serialized
    def list(self, user_id: str) -> list[ChatSession]:
        # Summaries only: messages are not loaded, since callers never read them here.
        rows = self.connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            [user_id],
        ).fetchall()

        return [
            ChatSession(
                id=row[0],
                title=row[1],
                created_at=row[2],
                updated_at=row[3],
            )
            for row in rows
        ]

    @_serialized
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
        title = session.title

        if role == "user" and title == "New chat":
            title = self._title_for(content)

        self.connection.execute(
            """
            INSERT INTO chat_messages
                (id, session_id, role, content, sources, model, truncated, usage,
                 duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                message.id,
                session_id,
                message.role,
                message.content,
                message.sources,
                message.model,
                message.truncated,
                message.usage,
                message.duration_ms,
                message.created_at,
            ],
        )
        for attachment in message.attachments:
            self.connection.execute(
                """
                INSERT INTO chat_attachments
                    (id, message_id, session_id, filename, media_type, size, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    attachment.id,
                    message.id,
                    session_id,
                    attachment.filename,
                    attachment.media_type,
                    attachment.size,
                    attachment.data,
                    utc_now(),
                ],
            )
        self.connection.execute(
            """
            UPDATE chat_sessions
            SET title = ?, updated_at = ?
            WHERE id = ?
            """,
            [title, utc_now(), session_id],
        )

        return message

    @_serialized
    def get_attachment(self, user_id: str, attachment_id: str) -> Attachment:
        row = self.connection.execute(
            """
            SELECT a.id, a.filename, a.media_type, a.size, a.data
            FROM chat_attachments AS a
            JOIN chat_sessions AS s ON s.id = a.session_id
            WHERE a.id = ? AND s.user_id = ?
            """,
            [attachment_id, user_id],
        ).fetchone()

        if row is None:
            raise KeyError(f"Attachment not found: {attachment_id}")

        attachment_id, filename, media_type, size, data = row
        return Attachment(
            id=attachment_id,
            filename=filename,
            media_type=media_type,
            size=size,
            data=bytes(data),
        )

    @_serialized
    def clear(self, user_id: str, session_id: str) -> ChatSession:
        self._require(user_id, session_id)
        updated_at = utc_now()

        self._delete_messages(session_id)
        self.connection.execute(
            """
            UPDATE chat_sessions
            SET title = 'New chat', updated_at = ?
            WHERE id = ?
            """,
            [updated_at, session_id],
        )

        cleared_session = self.get(user_id, session_id)

        if cleared_session is None:
            raise KeyError(f"Session not found: {session_id}")

        return cleared_session

    @_serialized
    def delete(self, user_id: str, session_id: str) -> None:
        self._require(user_id, session_id)

        self._delete_messages(session_id)
        self.connection.execute(
            "DELETE FROM chat_sessions WHERE id = ?",
            [session_id],
        )

    @_serialized
    def update(self, user_id: str, session_id: str, title: str) -> ChatSession:
        self._require(user_id, session_id)

        self.connection.execute(
            """
            UPDATE chat_sessions
            SET title = ?, updated_at = ?
            WHERE id = ?
            """,
            [title, utc_now(), session_id],
        )

        renamed_session = self.get(user_id, session_id)

        if renamed_session is None:
            raise KeyError(f"Session not found: {session_id}")

        return renamed_session

    @_serialized
    def close(self) -> None:
        self.connection.close()

    @_serialized
    def upsert_user(self, google_sub: str, email: str, name: str, picture: str) -> User:
        row = self.connection.execute(
            "SELECT id FROM users WHERE google_sub = ?",
            [google_sub],
        ).fetchone()

        if row is None:
            user_id = str(uuid4())
            self.connection.execute(
                """
                INSERT INTO users (id, google_sub, email, name, picture, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [user_id, google_sub, email, name, picture, utc_now()],
            )
        else:
            user_id = row[0]
            self.connection.execute(
                "UPDATE users SET email = ?, name = ?, picture = ? WHERE id = ?",
                [email, name, picture, user_id],
            )

        return User(id=user_id, google_sub=google_sub, email=email, name=name, picture=picture)

    @_serialized
    def get_user(self, user_id: str) -> User | None:
        row = self.connection.execute(
            "SELECT id, google_sub, email, name, picture FROM users WHERE id = ?",
            [user_id],
        ).fetchone()

        return User(*row) if row else None

    @_serialized
    def get_active_provider(self, user_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT active_provider FROM users WHERE id = ?",
            [user_id],
        ).fetchone()

        return row[0] if row else None

    @_serialized
    def set_active_provider(self, user_id: str, provider: str | None) -> None:
        self.connection.execute(
            "UPDATE users SET active_provider = ? WHERE id = ?",
            [provider, user_id],
        )

    @_serialized
    def count_users(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    @_serialized
    def claim_unowned_sessions(self, user_id: str) -> None:
        self.connection.execute(
            "UPDATE chat_sessions SET user_id = ? WHERE user_id IS NULL",
            [user_id],
        )

    @_serialized
    def save_refresh_token(self, token_hash: str, user_id: str, expires_at: str) -> None:
        self.connection.execute(
            """
            INSERT INTO refresh_tokens (token_hash, user_id, expires_at, revoked_at, created_at)
            VALUES (?, ?, ?, NULL, ?)
            """,
            [token_hash, user_id, expires_at, utc_now()],
        )

    @_serialized
    def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        row = self.connection.execute(
            "SELECT user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = ?",
            [token_hash],
        ).fetchone()

        if row is None:
            return None

        return RefreshToken(user_id=row[0], expires_at=row[1], revoked=row[2] is not None)

    @_serialized
    def revoke_refresh_token(self, token_hash: str) -> None:
        self.connection.execute(
            """
            UPDATE refresh_tokens SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            [utc_now(), token_hash],
        )

    @_serialized
    def revoke_user_refresh_tokens(self, user_id: str) -> None:
        self.connection.execute(
            """
            UPDATE refresh_tokens SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            [utc_now(), user_id],
        )

    @_serialized
    def save_api_key(self, user_id: str, provider: str, sealed: EncryptedKey, last4: str) -> None:
        now = utc_now()
        self.connection.execute(
            """
            INSERT INTO user_api_keys
                (user_id, provider, ciphertext, nonce, key_version, last4, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, provider) DO UPDATE SET
                ciphertext = excluded.ciphertext,
                nonce = excluded.nonce,
                key_version = excluded.key_version,
                last4 = excluded.last4,
                updated_at = excluded.updated_at
            """,
            [
                user_id,
                provider,
                sealed.ciphertext,
                sealed.nonce,
                sealed.key_version,
                last4,
                now,
                now,
            ],
        )

    @_serialized
    def get_api_key(self, user_id: str, provider: str) -> ApiKeyRecord | None:
        row = self.connection.execute(
            """
            SELECT provider, last4, updated_at, ciphertext, nonce, key_version
            FROM user_api_keys
            WHERE user_id = ? AND provider = ?
            """,
            [user_id, provider],
        ).fetchone()

        return _api_key_record(row) if row else None

    @_serialized
    def list_api_keys(self, user_id: str) -> list[ApiKeyRecord]:
        rows = self.connection.execute(
            """
            SELECT provider, last4, updated_at, ciphertext, nonce, key_version
            FROM user_api_keys
            WHERE user_id = ?
            ORDER BY provider
            """,
            [user_id],
        ).fetchall()

        return [_api_key_record(row) for row in rows]

    @_serialized
    def delete_api_key(self, user_id: str, provider: str) -> None:
        self.connection.execute(
            "DELETE FROM user_api_keys WHERE user_id = ? AND provider = ?",
            [user_id, provider],
        )

    @_serialized
    def record_audit_event(self, user_id: str, action: str, provider: str) -> None:
        self.connection.execute(
            """
            INSERT INTO audit_events (id, user_id, action, provider, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [str(uuid4()), user_id, action, provider, utc_now()],
        )

    @_serialized
    def list_audit_events(self, user_id: str) -> list[AuditEvent]:
        rows = self.connection.execute(
            """
            SELECT id, user_id, action, provider, created_at
            FROM audit_events
            WHERE user_id = ?
            ORDER BY created_at, id
            """,
            [user_id],
        ).fetchall()

        return [AuditEvent(*row) for row in rows]

    def _load_messages(self, session_id: str) -> list[ChatMessage]:
        message_rows = self.connection.execute(
            """
            SELECT id, role, content, sources, model, truncated, usage, duration_ms, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at, id
            """,
            [session_id],
        ).fetchall()

        attachment_rows = self.connection.execute(
            """
            SELECT id, message_id, filename, media_type, size
            FROM chat_attachments
            WHERE session_id = ?
            ORDER BY created_at, id
            """,
            [session_id],
        ).fetchall()
        attachments = attachments_by_message(attachment_rows)

        return [
            ChatMessage(
                id=message_id,
                role=role,
                content=content,
                created_at=created_at,
                sources=sources or "",
                model=model or "",
                truncated=bool(truncated),
                usage=usage or "",
                duration_ms=duration_ms,
                attachments=attachments.get(message_id, []),
            )
            for message_id, role, content, sources, model, truncated, usage, duration_ms, created_at
            in message_rows
        ]

    def _delete_messages(self, session_id: str) -> None:
        # Attachments reference their message, so they go first
        self.connection.execute(
            "DELETE FROM chat_attachments WHERE session_id = ?",
            [session_id],
        )
        self.connection.execute(
            "DELETE FROM chat_messages WHERE session_id = ?",
            [session_id],
        )

    def _initialize_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                created_at VARCHAR NOT NULL,
                updated_at VARCHAR NOT NULL
            )
            """
        )
        # Databases created before accounts existed need the owner column added in place.
        # Rows without an owner are invisible to every user until one claims them.
        self.connection.execute(
            "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_id VARCHAR"
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS chat_sessions_user_id_index
            ON chat_sessions (user_id)
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                model VARCHAR DEFAULT '',
                created_at VARCHAR NOT NULL
            )
            """
        )
        # Databases created before these columns existed need them added in place.
        self.connection.execute(
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS model VARCHAR DEFAULT ''"
        )
        self.connection.execute(
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS truncated BOOLEAN DEFAULT FALSE"
        )
        self.connection.execute(
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS usage TEXT"
        )
        self.connection.execute(
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS duration_ms INTEGER"
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS chat_messages_session_id_index
            ON chat_messages (session_id)
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_attachments (
                id VARCHAR PRIMARY KEY,
                message_id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL,
                filename VARCHAR NOT NULL,
                media_type VARCHAR NOT NULL,
                size BIGINT NOT NULL,
                data BLOB NOT NULL,
                created_at VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS chat_attachments_session_id_index
            ON chat_attachments (session_id)
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                google_sub VARCHAR NOT NULL UNIQUE,
                email VARCHAR NOT NULL,
                name VARCHAR NOT NULL DEFAULT '',
                picture VARCHAR NOT NULL DEFAULT '',
                created_at VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_provider VARCHAR"
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                expires_at VARCHAR NOT NULL,
                revoked_at VARCHAR,
                created_at VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS refresh_tokens_user_id_index
            ON refresh_tokens (user_id)
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                action VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                created_at VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_api_keys (
                user_id VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                ciphertext BLOB NOT NULL,
                nonce BLOB NOT NULL,
                key_version VARCHAR NOT NULL,
                last4 VARCHAR NOT NULL,
                created_at VARCHAR NOT NULL,
                updated_at VARCHAR NOT NULL,
                PRIMARY KEY (user_id, provider)
            )
            """
        )


def _api_key_record(row) -> ApiKeyRecord:
    provider, last4, updated_at, ciphertext, nonce, key_version = row
    return ApiKeyRecord(
        provider=provider,
        last4=last4,
        updated_at=updated_at,
        sealed=EncryptedKey(bytes(ciphertext), bytes(nonce), key_version),
    )
