import threading

import duckdb

from core.chat_core.duckdb_store import DuckDBSessionStore
from tests.support import USER_ID


def test_creates_chat_tables_in_memory():
    store = DuckDBSessionStore(":memory:")

    try:
        tables = store.connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchall()

        assert tables == [
            ("audit_events",),
            ("chat_attachments",),
            ("chat_messages",),
            ("chat_sessions",),
            ("refresh_tokens",),
            ("user_api_keys",),
            ("users",),
        ]
    finally:
        store.close()


def test_existing_database_gains_owner_column_and_legacy_sessions_can_be_claimed(tmp_path):
    path = str(tmp_path / "legacy.duckdb")
    # A database written before accounts existed: sessions have no owner column
    legacy = duckdb.connect(path)
    legacy.execute(
        """
        CREATE TABLE chat_sessions (
            id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            created_at VARCHAR NOT NULL,
            updated_at VARCHAR NOT NULL
        )
        """
    )
    legacy.execute(
        "INSERT INTO chat_sessions VALUES ('old-1', 'Old chat', '2024-01-01', '2024-01-01')"
    )
    legacy.close()

    store = DuckDBSessionStore(path)
    try:
        assert store.list(USER_ID) == []

        store.claim_unowned_sessions(USER_ID)

        assert [session.id for session in store.list(USER_ID)] == ["old-1"]
    finally:
        store.close()


def test_stores_model_on_messages():
    store = DuckDBSessionStore(":memory:")

    try:
        session = store.create(USER_ID)

        store.add_message(USER_ID, session.id, "user", "Hi")
        store.add_message(USER_ID, session.id, "assistant", "Hello", "[]", "claude-haiku-5-5")

        saved_session = store.get(USER_ID, session.id)

        assert saved_session is not None
        assert [message.model for message in saved_session.messages] == ["", "claude-haiku-5-5"]
        assert saved_session.to_dict()["messages"][1]["model"] == "claude-haiku-5-5"
    finally:
        store.close()


def test_stores_messages_and_clears_a_session():
    store = DuckDBSessionStore(":memory:")

    try:
        session = store.create(USER_ID)

        store.add_message(USER_ID, session.id, "user", "How does DuckDB work?")
        store.add_message(USER_ID, session.id, "assistant", "DuckDB is an embedded database.")

        saved_session = store.get(USER_ID, session.id)

        assert saved_session is not None
        assert saved_session.title == "How does DuckDB work?"
        assert [message.role for message in saved_session.messages] == [
            "user",
            "assistant",
        ]
        assert saved_session.messages[1].content == "DuckDB is an embedded database."

        cleared_session = store.clear(USER_ID, session.id)

        assert cleared_session.title == "New chat"
        assert cleared_session.messages == []
    finally:
        store.close()

def test_concurrent_reads_never_lose_sessions():
    store = DuckDBSessionStore(":memory:")
    session_ids = [store.create(USER_ID).id for _ in range(10)]
    missing = []

    def read_all():
        for _ in range(50):
            for session_id in session_ids:
                if store.get(USER_ID, session_id) is None:
                    missing.append(session_id)

    try:
        threads = [threading.Thread(target=read_all) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert missing == []
    finally:
        store.close()


def test_list_returns_summaries_without_messages():
    store = DuckDBSessionStore(":memory:")

    try:
        older = store.create(USER_ID)
        newer = store.create(USER_ID)
        store.add_message(USER_ID, older.id, "user", "Hello there")
        store.add_message(USER_ID, newer.id, "user", "Later")
        store.add_message(USER_ID, newer.id, "assistant", "Reply", "[]", "claude-haiku-5-5")

        sessions = store.list(USER_ID)

        assert [session.id for session in sessions] == [newer.id, older.id]
        assert all(session.messages == [] for session in sessions)
        assert sessions[1].title == "Hello there"
        assert sessions[0].to_dict(include_messages=False)["title"] == "Later"
    finally:
        store.close()


def test_adds_new_message_columns_to_existing_database(tmp_path):
    import duckdb

    database_path = str(tmp_path / "old.duckdb")
    old = duckdb.connect(database_path)
    old.execute(
        """
        CREATE TABLE chat_messages (
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
    old.execute(
        "INSERT INTO chat_messages VALUES ('m1', 's1', 'assistant', 'Old', '[]', 'm', '2026-01-01')"
    )
    old.close()

    store = DuckDBSessionStore(database_path)
    try:
        messages = store.connection.execute(
            "SELECT content, truncated, usage, duration_ms FROM chat_messages"
        ).fetchall()
        assert messages == [("Old", False, None, None)]
    finally:
        store.close()
