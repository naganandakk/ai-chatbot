import json

import pytest

from core.chat_core.key_vault import KeyVault
from core.chat_core.provider_pool import ProviderPool
from core.chat_core.providers import TextDelta
from core.chat_core.service import ApiKeyRequired, ChatService
from core.chat_core.store import InMemorySessionStore
from tests.support import OTHER_USER_ID, USER_ID


class ReplyingProvider:
    # Answers with the key it was built with, so a test can see which key a reply used
    def __init__(self, provider_name: str, api_key: str, max_tokens: int = 0) -> None:
        self.api_key = api_key

    def stream(self, *, model, messages, tools):
        yield TextDelta(f"answered with {self.api_key}")

    def close(self) -> None:
        pass


@pytest.fixture
def store_and_service(monkeypatch):
    # Pinned so the default does not depend on the developer's .env
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setattr("core.chat_core.provider_pool.create_provider_for", ReplyingProvider)
    store = InMemorySessionStore()
    service = ChatService(
        store=store,
        accounts=store,
        key_vault=KeyVault.from_env(),
        provider_pool=ProviderPool(),
    )
    return store, service


def save_key(store, user_id: str, provider: str, api_key: str) -> None:
    sealed = KeyVault.from_env().encrypt(user_id, provider, api_key)
    store.save_api_key(user_id, provider, sealed, api_key[-4:])


def drain(generator):
    chunks = []
    try:
        while True:
            chunks.append(next(generator))
    except StopIteration as finished:
        return "".join(chunks), finished.value


def test_each_user_replies_with_their_own_key(store_and_service):
    store, service = store_and_service
    save_key(store, USER_ID, "anthropic", "sk-ant-alice-key")
    save_key(store, OTHER_USER_ID, "anthropic", "sk-ant-bob-key")
    alice_chat = store.create(USER_ID)
    bob_chat = store.create(OTHER_USER_ID)

    alice_text, _ = drain(service.stream_reply(USER_ID, alice_chat.id, "Hi"))
    bob_text, _ = drain(service.stream_reply(OTHER_USER_ID, bob_chat.id, "Hi"))

    assert alice_text == "answered with sk-ant-alice-key"
    assert bob_text == "answered with sk-ant-bob-key"


def test_missing_key_stops_before_the_message_is_saved(store_and_service):
    store, service = store_and_service
    session = store.create(USER_ID)

    with pytest.raises(ApiKeyRequired):
        drain(service.stream_reply(USER_ID, session.id, "Hello"))

    assert store.get(USER_ID, session.id).messages == []


def test_a_provider_the_user_has_no_key_for_is_refused(store_and_service):
    store, service = store_and_service
    save_key(store, USER_ID, "anthropic", "sk-ant-alice-key")
    session = store.create(USER_ID)

    with pytest.raises(ApiKeyRequired):
        drain(service.stream_reply(USER_ID, session.id, "Hello", provider_name="openrouter"))


def test_unknown_provider_is_a_value_error(store_and_service):
    store, service = store_and_service
    session = store.create(USER_ID)

    with pytest.raises(ValueError, match="Unknown provider: nope"):
        drain(service.stream_reply(USER_ID, session.id, "Hello", provider_name="nope"))


def test_api_key_error_mentions_the_provider_but_never_a_key(store_and_service):
    store, service = store_and_service
    session = store.create(USER_ID)

    with pytest.raises(ApiKeyRequired) as error:
        drain(service.stream_reply(USER_ID, session.id, "Hello"))

    assert "anthropic" in str(error.value)
    assert "sk-" not in str(error.value)
    assert json.dumps({"message": str(error.value)})  # serializable for the SSE error event


def test_reply_uses_the_provider_the_user_chose_when_the_request_names_none(store_and_service):
    store, service = store_and_service
    save_key(store, USER_ID, "anthropic", "sk-ant-alice-key")
    save_key(store, USER_ID, "openrouter", "sk-or-alice-key")
    store.set_active_provider(USER_ID, "openrouter")
    session = store.create(USER_ID)

    text, _ = drain(service.stream_reply(USER_ID, session.id, "Hi"))

    assert text == "answered with sk-or-alice-key"
