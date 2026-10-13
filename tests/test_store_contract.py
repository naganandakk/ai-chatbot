import os

import psycopg
import pytest

from core.chat_core.duckdb_store import DuckDBSessionStore
from core.chat_core.key_vault import EncryptedKey
from core.chat_core.models import Attachment
from core.chat_core.postgres_store import PostgresSessionStore
from core.chat_core.store import InMemorySessionStore, SessionStore
from tests.support import OTHER_USER_ID, USER_ID

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
            connection.execute("TRUNCATE chat_attachments, chat_messages, chat_sessions, user_api_keys, refresh_tokens, users")

        yield store
        store.close()
        return

    store = DuckDBSessionStore(":memory:")
    yield store
    store.close()


def test_implementations_follow_the_store_contract(store):
    assert isinstance(store, SessionStore)


def test_update_renames_session(store):
    session = store.create(USER_ID)

    renamed = store.update(USER_ID, session.id, "Renamed")

    assert renamed.title == "Renamed"
    assert store.get(USER_ID, session.id).title == "Renamed"


def test_first_user_message_titles_session_and_truncates(store):
    session = store.create(USER_ID)

    store.add_message(USER_ID, session.id, "user", "x" * 60 + "\nmore")

    assert store.get(USER_ID, session.id).title == "x" * 48


def test_sources_and_model_are_saved_with_assistant_message(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Hi")

    store.add_message(USER_ID, session.id, "assistant", "Hello", '[{"title": "A", "url": "u"}]', "m-1")

    assistant = store.get(USER_ID, session.id).messages[1]
    assert assistant.sources == '[{"title": "A", "url": "u"}]'
    assert assistant.model == "m-1"


def test_clear_keeps_session_and_resets_title(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Question")

    cleared = store.clear(USER_ID, session.id)

    assert cleared.messages == []
    assert cleared.title == "New chat"
    assert store.get(USER_ID, session.id) is not None


def test_delete_removes_session(store):
    session = store.create(USER_ID)

    store.delete(USER_ID, session.id)

    assert store.get(USER_ID, session.id) is None


def test_list_returns_summaries_without_messages(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Hi")

    listed = store.list(USER_ID)

    assert [item.id for item in listed] == [session.id]
    assert all(item.messages == [] for item in listed)


@pytest.mark.parametrize(
    "call",
    [
        lambda store: store.clear(USER_ID, "missing"),
        lambda store: store.delete(USER_ID, "missing"),
        lambda store: store.update(USER_ID, "missing", "Title"),
        lambda store: store.add_message(USER_ID, "missing", "user", "Hi"),
    ],
)
def test_unknown_session_raises_key_error(store, call):
    with pytest.raises(KeyError, match="Session not found: missing"):
        call(store)


def test_truncated_flag_is_saved_with_assistant_message(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Hi")

    store.add_message(USER_ID, session.id, "assistant", "Partial", "[]", "m-1", truncated=True)

    assistant = store.get(USER_ID, session.id).messages[1]
    assert assistant.truncated is True
    assert assistant.to_dict()["truncated"] is True
    assert store.get(USER_ID, session.id).messages[0].truncated is False


def test_usage_is_saved_with_assistant_message(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Hi")

    store.add_message(USER_ID, session.id, "assistant", "Hello", "[]", "m-1", usage='{"input_tokens": 3}')

    assistant = store.get(USER_ID, session.id).messages[1]
    assert assistant.usage == '{"input_tokens": 3}'


def test_duration_is_saved_with_assistant_message(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Hi")

    store.add_message(USER_ID, session.id, "assistant", "Hello", duration_ms=1234)

    assert store.get(USER_ID, session.id).messages[1].duration_ms == 1234


def test_attachments_are_saved_with_their_message(store):
    session = store.create(USER_ID)
    attachment = Attachment(
        filename="notes.pdf", media_type="application/pdf", size=4, data=b"%PDF"
    )

    store.add_message(USER_ID, session.id, "user", "Read this", attachments=[attachment])

    saved = store.get(USER_ID, session.id).messages[0]
    assert [(a.id, a.filename, a.media_type, a.size) for a in saved.attachments] == [
        (attachment.id, "notes.pdf", "application/pdf", 4)
    ]
    # Session loads carry metadata only, never the bytes
    assert saved.attachments[0].data == b""
    assert store.get_attachment(USER_ID, attachment.id).data == b"%PDF"


def test_unknown_attachment_raises_key_error(store):
    with pytest.raises(KeyError):
        store.get_attachment(USER_ID, "missing")


def test_clear_and_delete_remove_attachments(store):
    session = store.create(USER_ID)
    attachment = Attachment(filename="a.png", media_type="image/png", size=3, data=b"abc")
    store.add_message(USER_ID, session.id, "user", "Look", attachments=[attachment])

    store.clear(USER_ID, session.id)

    with pytest.raises(KeyError):
        store.get_attachment(USER_ID, attachment.id)

    second = Attachment(filename="b.png", media_type="image/png", size=3, data=b"xyz")
    store.add_message(USER_ID, session.id, "user", "Again", attachments=[second])
    store.delete(USER_ID, session.id)

    with pytest.raises(KeyError):
        store.get_attachment(USER_ID, second.id)


def test_other_users_cannot_see_or_change_a_session(store):
    session = store.create(USER_ID)
    store.add_message(USER_ID, session.id, "user", "Private question")

    assert store.get(OTHER_USER_ID, session.id) is None
    assert store.list(OTHER_USER_ID) == []

    with pytest.raises(KeyError):
        store.add_message(OTHER_USER_ID, session.id, "user", "Hijack")
    with pytest.raises(KeyError):
        store.update(OTHER_USER_ID, session.id, "Renamed")
    with pytest.raises(KeyError):
        store.clear(OTHER_USER_ID, session.id)
    with pytest.raises(KeyError):
        store.delete(OTHER_USER_ID, session.id)

    # The owner's session is untouched by the attempts above
    saved = store.get(USER_ID, session.id)
    assert saved.title == "Private question"
    assert [message.content for message in saved.messages] == ["Private question"]


def test_other_users_cannot_read_attachments(store):
    session = store.create(USER_ID)
    attachment = Attachment(filename="a.png", media_type="image/png", size=3, data=b"abc")
    store.add_message(USER_ID, session.id, "user", "Look", attachments=[attachment])

    with pytest.raises(KeyError):
        store.get_attachment(OTHER_USER_ID, attachment.id)
    assert store.get_attachment(USER_ID, attachment.id).data == b"abc"


def test_each_user_lists_only_their_own_sessions(store):
    mine = store.create(USER_ID)
    theirs = store.create(OTHER_USER_ID)

    assert [session.id for session in store.list(USER_ID)] == [mine.id]
    assert [session.id for session in store.list(OTHER_USER_ID)] == [theirs.id]


def test_upsert_user_keeps_one_row_per_google_account(store):
    first = store.upsert_user("google-sub-1", "a@example.com", "Ada", "")
    again = store.upsert_user("google-sub-1", "ada@example.com", "Ada L", "pic.png")

    assert again.id == first.id
    assert store.get_user(first.id) == again
    assert store.count_users() == 1


def test_refresh_tokens_can_be_revoked_one_by_one_or_per_user(store):
    user = store.upsert_user("google-sub-1", "a@example.com", "Ada", "")
    store.save_refresh_token("hash-1", user.id, "2030-01-01T00:00:00+00:00")
    store.save_refresh_token("hash-2", user.id, "2030-01-01T00:00:00+00:00")

    store.revoke_refresh_token("hash-1")
    assert store.get_refresh_token("hash-1").revoked is True
    assert store.get_refresh_token("hash-2").revoked is False

    store.revoke_user_refresh_tokens(user.id)
    assert store.get_refresh_token("hash-2").revoked is True
    assert store.get_refresh_token("missing") is None


def test_api_key_is_saved_replaced_listed_and_deleted_per_user(store):
    user = store.upsert_user("google-sub-1", "a@example.com", "Ada", "")
    other = store.upsert_user("google-sub-2", "b@example.com", "Bo", "")
    first = EncryptedKey(b"cipher-1", b"nonce-1-123456", "v1")
    second = EncryptedKey(b"cipher-2", b"nonce-2-123456", "v1")

    store.save_api_key(user.id, "anthropic", first, "1234")
    store.save_api_key(user.id, "anthropic", second, "9876")

    saved = store.get_api_key(user.id, "anthropic")
    assert saved.sealed == second
    assert saved.last4 == "9876"
    assert [record.provider for record in store.list_api_keys(user.id)] == ["anthropic"]
    assert store.get_api_key(other.id, "anthropic") is None
    assert store.list_api_keys(other.id) == []

    store.delete_api_key(user.id, "anthropic")
    store.delete_api_key(user.id, "anthropic")
    assert store.get_api_key(user.id, "anthropic") is None


def test_api_key_seal_is_replaced_only_while_it_still_matches(store):
    user = store.upsert_user("google-sub-1", "a@example.com", "Ada", "")
    old = EncryptedKey(b"cipher-1", b"nonce-1-123456", "v1")
    new = EncryptedKey(b"cipher-2", b"nonce-2-123456", "v2")
    store.save_api_key(user.id, "anthropic", old, "1234")

    assert store.list_all_api_keys() == [(user.id, store.get_api_key(user.id, "anthropic"))]
    assert store.replace_api_key_seal(user.id, "anthropic", old, new) is True
    assert store.get_api_key(user.id, "anthropic").sealed == new
    assert store.get_api_key(user.id, "anthropic").last4 == "1234"

    # The row no longer holds `old`, so a second swap from it must be refused
    assert store.replace_api_key_seal(user.id, "anthropic", old, new) is False
    assert store.replace_api_key_seal(user.id, "openrouter", old, new) is False


def test_active_provider_defaults_to_none_and_can_be_changed(store):
    user = store.upsert_user("google-sub-3", "c@example.com", "Cy", "")
    assert store.get_active_provider(user.id) is None

    store.set_active_provider(user.id, "openrouter")
    assert store.get_active_provider(user.id) == "openrouter"

    store.set_active_provider(user.id, None)
    assert store.get_active_provider(user.id) is None


def test_audit_events_are_kept_per_user_in_order(store):
    user = store.upsert_user("google-sub-4", "d@example.com", "Di", "")
    other = store.upsert_user("google-sub-5", "e@example.com", "Ed", "")

    store.record_audit_event(user.id, "api_key.saved", "anthropic")
    store.record_audit_event(user.id, "api_key.deleted", "anthropic")

    events = store.list_audit_events(user.id)
    assert [(event.action, event.provider) for event in events] == [
        ("api_key.saved", "anthropic"),
        ("api_key.deleted", "anthropic"),
    ]
    assert store.list_audit_events(other.id) == []
