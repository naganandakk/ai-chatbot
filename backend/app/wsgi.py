import os
from pathlib import Path

from dotenv import load_dotenv

from core.chat_core.duckdb_store import DuckDBSessionStore
from core.chat_core.service import ChatService

from . import create_app

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

database_path = os.getenv("CHAT_DATABASE_PATH", "data/chat.duckdb")
tools_enabled_str = os.getenv("TOOLS_ENABLED", "").strip()
tools_enabled = []
if tools_enabled_str:
    tools_enabled = tools_enabled_str.split(",")

store=DuckDBSessionStore(database_path)
chat_service = ChatService(store=store, tools_enabled=tools_enabled)

app = create_app(
    store=store,
    chat_service=chat_service,
)