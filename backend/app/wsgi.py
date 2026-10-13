from pathlib import Path

from dotenv import load_dotenv

from core.chat_core.key_vault import KeyVault
from core.chat_core.service import ChatService
from core.chat_core.stores import create_store

from . import create_app

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

store = create_store()
key_vault = KeyVault.from_env()
# Each user replies with their own saved API key, so there is no server-wide key to warm up
chat_service = ChatService(
    store=store,
    accounts=store,
    key_vault=key_vault,
)

app = create_app(
    store=store,
    chat_service=chat_service,
    key_vault=key_vault,
)
