import os

import psycopg
import pytest

from core.chat_core.duckdb_store import DuckDBSessionStore
from core.chat_core.postgres_store import PostgresSessionStore
from core.chat_core.store import InMemorySessionStore, SessionStore

# Point this at a disposable database to run the Postgres contract checks. Its tables are
# emptied before each test, so never use a database holding data you want to keep.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


@pytest.fixture(
    params=[
        "memory",
        "duckdb",
        pytest.param(
            "postgres",
            marks=pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"),
        ),
    ]
)
def store(request):
    if request.param == "memory":
        yield InMemorySessionStore()
        return

    if request.param == "postgres":
        store = PostgresSessionStore(TEST_DATABASE_URL)
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
            connection.execute("TRUNCATE chat_messages, chat_sessions")

        yield store
        store.close()
        return

    store = DuckDBSessionStore(":memory:")
    yield store
    store.close()


def test_implementations_follow_the_store_contract(store):
    assert isinstance(store, SessionStore)


def test_update_renames_session(store):
    session = store.create()

    renamed = store.update(session.id, "Renamed")

    assert renamed.title == "Renamed"
    assert store.get(session.id).title == "Renamed"


def test_first_user_message_titles_session_and_truncates(store):
    session = store.create()

    store.add_message(session.id, "user", "x" * 60 + "\nmore")

    assert store.get(session.id).title == "x" * 48


def test_sources_and_model_are_saved_with_assistant_message(store):
    session = store.create()
    store.add_message(session.id, "user", "Hi")

    store.add_message(session.id, "assistant", "Hello", '[{"title": "A", "url": "u"}]', "m-1")

    assistant = store.get(session.id).messages[1]
    assert assistant.sources == '[{"title": "A", "url": "u"}]'
    assert assistant.model == "m-1"


def test_clear_keeps_session_and_resets_title(store):
    session = store.create()
    store.add_message(session.id, "user", "Question")

    cleared = store.clear(session.id)

    assert cleared.messages == []
    assert cleared.title == "New chat"
    assert store.get(session.id) is not None


def test_delete_removes_session(store):
    session = store.create()

    store.delete(session.id)

    assert store.get(session.id) is None


def test_list_returns_summaries_without_messages(store):
    session = store.create()
    store.add_message(session.id, "user", "Hi")

    listed = store.list()

    assert [item.id for item in listed] == [session.id]
    assert all(item.messages == [] for item in listed)


@pytest.mark.parametrize(
    "call",
    [
        lambda store: store.clear("missing"),
        lambda store: store.delete("missing"),
        lambda store: store.update("missing", "Title"),
        lambda store: store.add_message("missing", "user", "Hi"),
    ],
)
def test_unknown_session_raises_key_error(store, call):
    with pytest.raises(KeyError, match="Session not found: missing"):
        call(store)


def test_truncated_flag_is_saved_with_assistant_message(store):
    session = store.create()
    store.add_message(session.id, "user", "Hi")

    store.add_message(session.id, "assistant", "Partial", "[]", "m-1", truncated=True)

    assistant = store.get(session.id).messages[1]
    assert assistant.truncated is True
    assert assistant.to_dict()["truncated"] is True
    assert store.get(session.id).messages[0].truncated is False


def test_usage_is_saved_with_assistant_message(store):
    session = store.create()
    store.add_message(session.id, "user", "Hi")

    store.add_message(session.id, "assistant", "Hello", "[]", "m-1", usage='{"input_tokens": 3}')

    assistant = store.get(session.id).messages[1]
    assert assistant.usage == '{"input_tokens": 3}'


def test_duration_is_saved_with_assistant_message(store):
    session = store.create()
    store.add_message(session.id, "user", "Hi")

    store.add_message(session.id, "assistant", "Hello", duration_ms=1234)

    assert store.get(session.id).messages[1].duration_ms == 1234
