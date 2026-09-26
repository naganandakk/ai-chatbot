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