from __future__ import annotations

import threading
from collections.abc import Sequence
from functools import wraps
from pathlib import Path

import duckdb

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


class DuckDBSessionStore(SessionStore):
    def __init__(self, database_path: str) -> None:
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self.connection = duckdb.connect(database_path)
        self._initialize_schema()

    @_serialized
    def create(self) -> ChatSession:
        session = ChatSession()

        self.connection.execute(
            """
            INSERT INTO chat_sessions (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                session.id,
                session.title,
                session.created_at,
                session.updated_at,
            ],
        )

        return session

    @_serialized
    def get(self, session_id: str) -> ChatSession | None:
        row = self.connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = ?
            """,
            [session_id],
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
    def list(self) -> list[ChatSession]:
        # Summaries only: messages are not loaded, since callers never read them here.
        rows = self.connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            ORDER BY created_at DESC
            """
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
        session = self._require(session_id)
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
    def get_attachment(self, attachment_id: str) -> Attachment:
        row = self.connection.execute(
            "SELECT id, filename, media_type, size, data FROM chat_attachments WHERE id = ?",
            [attachment_id],
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
    def clear(self, session_id: str) -> ChatSession:
        self._require(session_id)
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

        cleared_session = self.get(session_id)

        if cleared_session is None:
            raise KeyError(f"Session not found: {session_id}")

        return cleared_session

    @_serialized
    def delete(self, session_id: str) -> None:
        self._require(session_id)

        self._delete_messages(session_id)
        self.connection.execute(
            "DELETE FROM chat_sessions WHERE id = ?",
            [session_id],
        )

    @_serialized
    def update(self, session_id: str, title: str) -> ChatSession:
        self._require(session_id)

        self.connection.execute(
            """
            UPDATE chat_sessions
            SET title = ?, updated_at = ?
            WHERE id = ?
            """,
            [title, utc_now(), session_id],
        )

        renamed_session = self.get(session_id)

        if renamed_session is None:
            raise KeyError(f"Session not found: {session_id}")

        return renamed_session

    @_serialized
    def close(self) -> None:
        self.connection.close()

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

