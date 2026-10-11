import os
from pathlib import Path

from dotenv import load_dotenv

from core.chat_core.service import ChatService
from core.chat_core.stores import create_store

from . import create_app

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

tools_enabled_str = os.getenv("TOOLS_ENABLED", "").strip()
tools_enabled = []
if tools_enabled_str:
    tools_enabled = tools_enabled_str.split(",")

store = create_store()
chat_service = ChatService(store=store, tools_enabled=tools_enabled)
chat_service.warm_up()

app = create_app(
    store=store,
    chat_service=chat_service,
)