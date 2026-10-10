import threading

from core.chat_core.duckdb_store import DuckDBSessionStore


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
            ("chat_messages",),
            ("chat_sessions",),
        ]
    finally:
        store.close()

def test_stores_model_on_messages():
    store = DuckDBSessionStore(":memory:")

    try:
        session = store.create()

        store.add_message(session.id, "user", "Hi")
        store.add_message(session.id, "assistant", "Hello", "[]", "claude-haiku-5-5")

        saved_session = store.get(session.id)

        assert saved_session is not None
        assert [message.model for message in saved_session.messages] == ["", "claude-haiku-5-5"]
        assert saved_session.to_dict()["messages"][1]["model"] == "claude-haiku-5-5"
    finally:
        store.close()


def test_stores_messages_and_clears_a_session():
    store = DuckDBSessionStore(":memory:")

    try:
        session = store.create()

        store.add_message(session.id, "user", "How does DuckDB work?")
        store.add_message(session.id, "assistant", "DuckDB is an embedded database.")

        saved_session = store.get(session.id)

        assert saved_session is not None
        assert saved_session.title == "How does DuckDB work?"
        assert [message.role for message in saved_session.messages] == [
            "user",
            "assistant",
        ]
        assert saved_session.messages[1].content == "DuckDB is an embedded database."

        cleared_session = store.clear(session.id)

        assert cleared_session.title == "New chat"
        assert cleared_session.messages == []
    finally:
        store.close()

def test_concurrent_reads_never_lose_sessions():
    store = DuckDBSessionStore(":memory:")
    session_ids = [store.create().id for _ in range(10)]
    missing = []

    def read_all():
        for _ in range(50):
            for session_id in session_ids:
                if store.get(session_id) is None:
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
        older = store.create()
        newer = store.create()
        store.add_message(older.id, "user", "Hello there")
        store.add_message(newer.id, "user", "Later")
        store.add_message(newer.id, "assistant", "Reply", "[]", "claude-haiku-5-5")

        sessions = store.list()

        assert [session.id for session in sessions] == [newer.id, older.id]
        assert all(session.messages == [] for session in sessions)
        assert sessions[1].title == "Hello there"
        assert sessions[0].to_dict(include_messages=False)["title"] == "Later"
    finally:
        store.close()


def test_adds_truncated_column_to_existing_database(tmp_path):
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
            "SELECT content, truncated FROM chat_messages"
        ).fetchall()
        assert messages == [("Old", False)]
    finally:
        store.close()
