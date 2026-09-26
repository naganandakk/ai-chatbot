import os
from pathlib import Path

from dotenv import load_dotenv

from core.chat_core.duckdb_store import DuckDBSessionStore

from . import create_app

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

database_path = os.getenv("CHAT_DATABASE_PATH", "data/chat.duckdb")

app = create_app(
    store=DuckDBSessionStore(database_path),
)