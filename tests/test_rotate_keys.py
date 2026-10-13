import base64

import pytest

from backend.app import rotate_keys
from core.chat_core.key_vault import KeyVault
from core.chat_core.store import InMemorySessionStore
from tests.support import OTHER_USER_ID, USER_ID

OLD_KEY = bytes(range(32))
NEW_KEY = bytes(range(32, 64))
SECRET = "sk-ant-test-secret-value"


@pytest.fixture
def store(monkeypatch):
    store = InMemorySessionStore()
    store.upsert_user("google-sub-1", "a@example.com", "Ada", "")
    store.upsert_user("google-sub-2", "b@example.com", "Bo", "")
    monkeypatch.setattr(rotate_keys, "create_store", lambda: store)
    return store


def _use_keys(monkeypatch, *keys):
    encoded = ",".join(base64.b64encode(key).decode() for key in keys)
    monkeypatch.setenv("KEY_ENCRYPTION_KEYS", encoded)


def test_moves_old_rows_onto_the_new_key(store, monkeypatch, capsys):
    old_vault = KeyVault([OLD_KEY])
    store.save_api_key(USER_ID, "anthropic", old_vault.encrypt(USER_ID, "anthropic", SECRET), "1234")
    store.save_api_key(
        OTHER_USER_ID, "openrouter", old_vault.encrypt(OTHER_USER_ID, "openrouter", SECRET), "9876"
    )
    _use_keys(monkeypatch, NEW_KEY, OLD_KEY)

    assert rotate_keys.main([]) == 0

    new_vault = KeyVault([NEW_KEY])
    for user_id, provider in [(USER_ID, "anthropic"), (OTHER_USER_ID, "openrouter")]:
        record = store.get_api_key(user_id, provider)
        assert record.sealed.key_version == new_vault.current_version
        assert new_vault.decrypt(user_id, provider, record.sealed) == SECRET

    assert store.get_api_key(USER_ID, "anthropic").last4 == "1234"
    assert [event.action for event in store.list_audit_events(USER_ID)] == ["rekey"]
    output = capsys.readouterr().out
    assert "moved=2" in output
    assert SECRET not in output


def test_dry_run_changes_nothing(store, monkeypatch, capsys):
    old_vault = KeyVault([OLD_KEY])
    sealed = old_vault.encrypt(USER_ID, "anthropic", SECRET)
    store.save_api_key(USER_ID, "anthropic", sealed, "1234")
    _use_keys(monkeypatch, NEW_KEY, OLD_KEY)

    assert rotate_keys.main(["--dry-run"]) == 0

    assert store.get_api_key(USER_ID, "anthropic").sealed == sealed
    assert store.list_audit_events(USER_ID) == []
    assert "WOULD MOVE" in capsys.readouterr().out


def test_rows_already_on_the_current_key_are_left_alone(store, monkeypatch, capsys):
    current = KeyVault([NEW_KEY, OLD_KEY]).encrypt(USER_ID, "anthropic", SECRET)
    store.save_api_key(USER_ID, "anthropic", current, "1234")
    _use_keys(monkeypatch, NEW_KEY, OLD_KEY)

    assert rotate_keys.main([]) == 0

    assert store.get_api_key(USER_ID, "anthropic").sealed == current
    assert "already_current=1" in capsys.readouterr().out


def test_row_whose_old_key_was_removed_is_reported_and_fails_the_run(store, monkeypatch, capsys):
    sealed = KeyVault([OLD_KEY]).encrypt(USER_ID, "anthropic", SECRET)
    store.save_api_key(USER_ID, "anthropic", sealed, "1234")
    _use_keys(monkeypatch, NEW_KEY)

    assert rotate_keys.main([]) == 1

    assert store.get_api_key(USER_ID, "anthropic").sealed == sealed
    assert "FAILED" in capsys.readouterr().out
