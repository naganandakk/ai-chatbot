import os

from .duckdb_store import DuckDBSessionStore
from .postgres_store import PostgresSessionStore
from .store import SessionStore

STORE_NAMES = ("duckdb", "postgres")


def create_store() -> SessionStore:
    """Build the session store named by CHAT_STORE (default: duckdb)."""
    store_name = os.getenv("CHAT_STORE", "duckdb").strip().lower()

    if store_name == "duckdb":
        return DuckDBSessionStore(os.getenv("CHAT_DATABASE_PATH", "data/chat.duckdb"))

    if store_name == "postgres":
        database_url = os.getenv("DATABASE_URL", "").strip()

        if not database_url:
            raise RuntimeError("DATABASE_URL is required when CHAT_STORE=postgres")

        return PostgresSessionStore(database_url)

    raise RuntimeError(f"CHAT_STORE must be 'duckdb' or 'postgres', got {store_name!r}")
