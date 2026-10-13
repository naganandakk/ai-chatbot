from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from psycopg import Connection
from psycopg_pool import ConnectionPool

from .accounts import AccountStore, ApiKeyRecord, AuditEvent, RefreshToken, User
from .key_vault import EncryptedKey
from .models import Attachment, ChatMessage, ChatSession, attachments_by_message, utc_now
from .store import SessionStore

# Timestamps stay as ISO-8601 text, matching the DuckDB store and the API's string dates.
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    # Databases created before accounts existed get the owner column in place. Rows
    # without an owner are invisible to every user until one claims them.
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_id TEXT",
    """
    CREATE INDEX IF NOT EXISTS chat_sessions_user_id_index
    ON chat_sessions (user_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions (id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        sources TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '',
        truncated BOOLEAN NOT NULL DEFAULT FALSE,
        usage TEXT NOT NULL DEFAULT '',
        duration_ms INTEGER,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS chat_messages_session_id_index
    ON chat_messages (session_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_attachments (
        id TEXT PRIMARY KEY,
        message_id TEXT NOT NULL REFERENCES chat_messages (id),
        session_id TEXT NOT NULL REFERENCES chat_sessions (id),
        filename TEXT NOT NULL,
        media_type TEXT NOT NULL,
        size INTEGER NOT NULL,
        data BYTEA NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS chat_attachments_session_id_index
    ON chat_attachments (session_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        google_sub TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        picture TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    # Databases created before the provider choice existed get the column in place
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_provider TEXT",
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users (id),
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS refresh_tokens_user_id_index
    ON refresh_tokens (user_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        provider TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS audit_events_user_id_index
    ON audit_events (user_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS user_api_keys (
        user_id TEXT NOT NULL REFERENCES users (id),
        provider TEXT NOT NULL,
        ciphertext BYTEA NOT NULL,
        nonce BYTEA NOT NULL,
        key_version TEXT NOT NULL,
        last4 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, provider)
    )
    """,
]


class PostgresSessionStore(SessionStore, AccountStore):
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 5) -> None:
        # Each request borrows its own connection, so threads and workers do not share one.
        self._pool = ConnectionPool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            open=True,
        )
        self._initialize_schema()

    def create(self, user_id: str) -> ChatSession:
        session = ChatSession()

        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [session.id, user_id, session.title, session.created_at, session.updated_at],
            )

        return session

    def get(self, user_id: str, session_id: str) -> ChatSession | None:
        with self._pool.connection() as connection:
            return self._load(connection, user_id, session_id)

    def list(self, user_id: str) -> list[ChatSession]:
        # Summaries only: messages are not loaded, since callers never read them here.
        with self._pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                [user_id],
            ).fetchall()

        return [
            ChatSession(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])
            for row in rows
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

        with self._pool.connection() as connection:
            title = self._lock_session(connection, user_id, session_id)

            if role == "user" and title == "New chat":
                title = self._title_for(content)

            connection.execute(
                """
                INSERT INTO chat_messages
                    (id, session_id, role, content, sources, model, truncated, usage,
                     duration_ms, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                connection.execute(
                    """
                    INSERT INTO chat_attachments
                        (id, message_id, session_id, filename, media_type, size, data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
            connection.execute(
                "UPDATE chat_sessions SET title = %s, updated_at = %s WHERE id = %s",
                [title, utc_now(), session_id],
            )

        return message

    def get_attachment(self, user_id: str, attachment_id: str) -> Attachment:
        with self._pool.connection() as connection:
            row = connection.execute(
                """
                SELECT a.id, a.filename, a.media_type, a.size, a.data
                FROM chat_attachments AS a
                JOIN chat_sessions AS s ON s.id = a.session_id
                WHERE a.id = %s AND s.user_id = %s
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
            # psycopg returns bytea as a memoryview
            data=bytes(data),
        )

    def clear(self, user_id: str, session_id: str) -> ChatSession:
        with self._pool.connection() as connection:
            self._lock_session(connection, user_id, session_id)
            self._delete_messages(connection, session_id)

            connection.execute(
                """
                UPDATE chat_sessions
                SET title = 'New chat', updated_at = %s
                WHERE id = %s
                """,
                [utc_now(), session_id],
            )

            return self._load(connection, user_id, session_id)

    def delete(self, user_id: str, session_id: str) -> None:
        with self._pool.connection() as connection:
            self._lock_session(connection, user_id, session_id)
            self._delete_messages(connection, session_id)
            connection.execute("DELETE FROM chat_sessions WHERE id = %s", [session_id])

    def update(self, user_id: str, session_id: str, title: str) -> ChatSession:
        with self._pool.connection() as connection:
            self._lock_session(connection, user_id, session_id)

            connection.execute(
                """
                UPDATE chat_sessions
                SET title = %s, updated_at = %s
                WHERE id = %s
                """,
                [title, utc_now(), session_id],
            )

            return self._load(connection, user_id, session_id)

    def close(self) -> None:
        self._pool.close()

    def upsert_user(self, google_sub: str, email: str, name: str, picture: str) -> User:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT id FROM users WHERE google_sub = %s FOR UPDATE",
                [google_sub],
            ).fetchone()

            if row is None:
                user_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO users (id, google_sub, email, name, picture, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [user_id, google_sub, email, name, picture, utc_now()],
                )
            else:
                user_id = row[0]
                connection.execute(
                    "UPDATE users SET email = %s, name = %s, picture = %s WHERE id = %s",
                    [email, name, picture, user_id],
                )

        return User(id=user_id, google_sub=google_sub, email=email, name=name, picture=picture)

    def get_user(self, user_id: str) -> User | None:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT id, google_sub, email, name, picture FROM users WHERE id = %s",
                [user_id],
            ).fetchone()

        return User(*row) if row else None

    def get_active_provider(self, user_id: str) -> str | None:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT active_provider FROM users WHERE id = %s",
                [user_id],
            ).fetchone()

        return row[0] if row else None

    def set_active_provider(self, user_id: str, provider: str | None) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                "UPDATE users SET active_provider = %s WHERE id = %s",
                [provider, user_id],
            )

    def count_users(self) -> int:
        with self._pool.connection() as connection:
            return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def claim_unowned_sessions(self, user_id: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                "UPDATE chat_sessions SET user_id = %s WHERE user_id IS NULL",
                [user_id],
            )

    def save_refresh_token(self, token_hash: str, user_id: str, expires_at: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO refresh_tokens (token_hash, user_id, expires_at, revoked_at, created_at)
                VALUES (%s, %s, %s, NULL, %s)
                """,
                [token_hash, user_id, expires_at, utc_now()],
            )

    def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = %s",
                [token_hash],
            ).fetchone()

        if row is None:
            return None

        return RefreshToken(user_id=row[0], expires_at=row[1], revoked=row[2] is not None)

    def revoke_refresh_token(self, token_hash: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                UPDATE refresh_tokens SET revoked_at = %s
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                [utc_now(), token_hash],
            )

    def revoke_user_refresh_tokens(self, user_id: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                UPDATE refresh_tokens SET revoked_at = %s
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                [utc_now(), user_id],
            )

    def save_api_key(self, user_id: str, provider: str, sealed: EncryptedKey, last4: str) -> None:
        now = utc_now()
        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO user_api_keys
                    (user_id, provider, ciphertext, nonce, key_version, last4, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, provider) DO UPDATE SET
                    ciphertext = EXCLUDED.ciphertext,
                    nonce = EXCLUDED.nonce,
                    key_version = EXCLUDED.key_version,
                    last4 = EXCLUDED.last4,
                    updated_at = EXCLUDED.updated_at
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

    def get_api_key(self, user_id: str, provider: str) -> ApiKeyRecord | None:
        with self._pool.connection() as connection:
            row = connection.execute(
                """
                SELECT provider, last4, updated_at, ciphertext, nonce, key_version
                FROM user_api_keys
                WHERE user_id = %s AND provider = %s
                """,
                [user_id, provider],
            ).fetchone()

        return _api_key_record(row) if row else None

    def list_api_keys(self, user_id: str) -> list[ApiKeyRecord]:
        with self._pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT provider, last4, updated_at, ciphertext, nonce, key_version
                FROM user_api_keys
                WHERE user_id = %s
                ORDER BY provider
                """,
                [user_id],
            ).fetchall()

        return [_api_key_record(row) for row in rows]

    def delete_api_key(self, user_id: str, provider: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                "DELETE FROM user_api_keys WHERE user_id = %s AND provider = %s",
                [user_id, provider],
            )

    def record_audit_event(self, user_id: str, action: str, provider: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (id, user_id, action, provider, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [str(uuid4()), user_id, action, provider, utc_now()],
            )

    def list_audit_events(self, user_id: str) -> list[AuditEvent]:
        with self._pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, action, provider, created_at
                FROM audit_events
                WHERE user_id = %s
                ORDER BY created_at, id
                """,
                [user_id],
            ).fetchall()

        return [AuditEvent(*row) for row in rows]

    def _lock_session(self, connection: Connection, user_id: str, session_id: str) -> str:
        # Row lock so concurrent writes to one session apply their title changes in order.
        row = connection.execute(
            "SELECT title FROM chat_sessions WHERE id = %s AND user_id = %s FOR UPDATE",
            [session_id, user_id],
        ).fetchone()

        if row is None:
            raise KeyError(f"Session not found: {session_id}")

        return row[0]

    def _delete_messages(self, connection: Connection, session_id: str) -> None:
        # Attachments reference their message, so they go first
        connection.execute("DELETE FROM chat_attachments WHERE session_id = %s", [session_id])
        connection.execute("DELETE FROM chat_messages WHERE session_id = %s", [session_id])

    def _load(self, connection: Connection, user_id: str, session_id: str) -> ChatSession | None:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = %s AND user_id = %s
            """,
            [session_id, user_id],
        ).fetchone()

        if row is None:
            return None

        message_rows = connection.execute(
            """
            SELECT id, role, content, sources, model, truncated, usage, duration_ms, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at, id
            """,
            [session_id],
        ).fetchall()

        attachment_rows = connection.execute(
            """
            SELECT id, message_id, filename, media_type, size
            FROM chat_attachments
            WHERE session_id = %s
            ORDER BY created_at, id
            """,
            [session_id],
        ).fetchall()
        attachments = attachments_by_message(attachment_rows)

        messages = [
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

        return ChatSession(
            id=row[0],
            title=row[1],
            messages=messages,
            created_at=row[2],
            updated_at=row[3],
        )

    def _initialize_schema(self) -> None:
        with self._pool.connection() as connection:
            # Serializes schema creation when several workers start at the same moment.
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('chat_schema'))")
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)


def _api_key_record(row) -> ApiKeyRecord:
    provider, last4, updated_at, ciphertext, nonce, key_version = row
    return ApiKeyRecord(
        provider=provider,
        last4=last4,
        updated_at=updated_at,
        # psycopg returns bytea as a memoryview
        sealed=EncryptedKey(bytes(ciphertext), bytes(nonce), key_version),
    )
