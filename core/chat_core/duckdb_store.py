from pathlib import Path
from uuid import uuid4

import duckdb

from .models import ChatMessage, ChatSession, utc_now


class DuckDBSessionStore:
    def __init__(self, database_path: str) -> None:
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        self.connection = duckdb.connect(database_path)
        self._initialize_schema()

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

        message_rows = self.connection.execute(
            """
            SELECT role, content, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at, id
            """,
            [session_id],
        ).fetchall()

        messages = [
            ChatMessage(role=role, content=content, created_at=created_at)
            for role, content, created_at in message_rows
        ]

        return ChatSession(
            id=row[0],
            title=row[1],
            messages=messages,
            created_at=row[2],
            updated_at=row[3],
        )

    def list(self) -> list[ChatSession]:
        rows = self.connection.execute(
            """
            SELECT id
            FROM chat_sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()

        return [
            session
            for (session_id,) in rows
            if (session := self.get(session_id)) is not None
        ]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> ChatMessage:
        session = self._require(session_id)
        message = ChatMessage(role=role, content=content)
        title = session.title

        if role == "user" and title == "New chat":
            title = self._title_for(content)

        self.connection.execute(
            """
            INSERT INTO chat_messages (id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                str(uuid4()),
                session_id,
                message.role,
                message.content,
                message.created_at,
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

    def clear(self, session_id: str) -> ChatSession:
        self._require(session_id)
        updated_at = utc_now()

        self.connection.execute(
            "DELETE FROM chat_messages WHERE session_id = ?",
            [session_id],
        )
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

    def delete(self, session_id: str) -> None:
        self._require(session_id)

        self.connection.execute(
            "DELETE FROM chat_messages WHERE session_id = ?",
            [session_id],
        )
        self.connection.execute(
            "DELETE FROM chat_sessions WHERE id = ?",
            [session_id],
        )

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

    def close(self) -> None:
        self.connection.close()

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
                created_at VARCHAR NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS chat_messages_session_id_index
            ON chat_messages (session_id)
            """
        )

    def _require(self, session_id: str) -> ChatSession:
        session = self.get(session_id)

        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        return session

    @staticmethod
    def _title_for(content: str) -> str:
        normalized = content.strip().replace("\n", " ")
        return normalized[:48] or "New chat"