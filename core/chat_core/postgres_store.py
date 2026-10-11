from uuid import uuid4

from psycopg import Connection
from psycopg_pool import ConnectionPool

from .models import ChatMessage, ChatSession, utc_now
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
]


class PostgresSessionStore(SessionStore):
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 5) -> None:
        # Each request borrows its own connection, so threads and workers do not share one.
        self._pool = ConnectionPool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            open=True,
        )
        self._initialize_schema()

    def create(self) -> ChatSession:
        session = ChatSession()

        with self._pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_sessions (id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                """,
                [session.id, session.title, session.created_at, session.updated_at],
            )

        return session

    def get(self, session_id: str) -> ChatSession | None:
        with self._pool.connection() as connection:
            return self._load(connection, session_id)

    def list(self) -> list[ChatSession]:
        # Summaries only: messages are not loaded, since callers never read them here.
        with self._pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM chat_sessions
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [
            ChatSession(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])
            for row in rows
        ]

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
    ) -> ChatMessage:
        message = ChatMessage(
            role=role,
            content=content,
            sources=sources,
            model=model,
            truncated=truncated,
            usage=usage,
            duration_ms=duration_ms,
        )

        with self._pool.connection() as connection:
            title = self._lock_session(connection, session_id)

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
                    str(uuid4()),
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
            connection.execute(
                "UPDATE chat_sessions SET title = %s, updated_at = %s WHERE id = %s",
                [title, utc_now(), session_id],
            )

        return message

    def clear(self, session_id: str) -> ChatSession:
        with self._pool.connection() as connection:
            self._lock_session(connection, session_id)

            connection.execute(
                "DELETE FROM chat_messages WHERE session_id = %s",
                [session_id],
            )
            connection.execute(
                """
                UPDATE chat_sessions
                SET title = 'New chat', updated_at = %s
                WHERE id = %s
                """,
                [utc_now(), session_id],
            )

            return self._load(connection, session_id)

    def delete(self, session_id: str) -> None:
        with self._pool.connection() as connection:
            self._lock_session(connection, session_id)

            connection.execute(
                "DELETE FROM chat_messages WHERE session_id = %s",
                [session_id],
            )
            connection.execute("DELETE FROM chat_sessions WHERE id = %s", [session_id])

    def update(self, session_id: str, title: str) -> ChatSession:
        with self._pool.connection() as connection:
            self._lock_session(connection, session_id)

            connection.execute(
                """
                UPDATE chat_sessions
                SET title = %s, updated_at = %s
                WHERE id = %s
                """,
                [title, utc_now(), session_id],
            )

            return self._load(connection, session_id)

    def close(self) -> None:
        self._pool.close()

    def _lock_session(self, connection: Connection, session_id: str) -> str:
        # Row lock so concurrent writes to one session apply their title changes in order.
        row = connection.execute(
            "SELECT title FROM chat_sessions WHERE id = %s FOR UPDATE",
            [session_id],
        ).fetchone()

        if row is None:
            raise KeyError(f"Session not found: {session_id}")

        return row[0]

    def _load(self, connection: Connection, session_id: str) -> ChatSession | None:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = %s
            """,
            [session_id],
        ).fetchone()

        if row is None:
            return None

        message_rows = connection.execute(
            """
            SELECT role, content, sources, model, truncated, usage, duration_ms, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at, id
            """,
            [session_id],
        ).fetchall()

        messages = [
            ChatMessage(
                role=role,
                content=content,
                created_at=created_at,
                sources=sources or "",
                model=model or "",
                truncated=bool(truncated),
                usage=usage or "",
                duration_ms=duration_ms,
            )
            for role, content, sources, model, truncated, usage, duration_ms, created_at
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
