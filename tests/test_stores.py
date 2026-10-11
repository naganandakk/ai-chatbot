import pytest

from core.chat_core.duckdb_store import DuckDBSessionStore
from core.chat_core.stores import create_store


def test_defaults_to_duckdb(monkeypatch, tmp_path):
    monkeypatch.delenv("CHAT_STORE", raising=False)
    monkeypatch.setenv("CHAT_DATABASE_PATH", str(tmp_path / "chat.duckdb"))

    store = create_store()

    try:
        assert isinstance(store, DuckDBSessionStore)
    finally:
        store.close()


def test_postgres_requires_database_url(monkeypatch):
    monkeypatch.setenv("CHAT_STORE", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        create_store()


def test_rejects_unknown_store(monkeypatch):
    monkeypatch.setenv("CHAT_STORE", "mysql")

    with pytest.raises(RuntimeError, match="CHAT_STORE must be 'duckdb' or 'postgres'"):
        create_store()
