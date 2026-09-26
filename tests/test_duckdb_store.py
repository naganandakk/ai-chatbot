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