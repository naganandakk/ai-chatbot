import base64
import os

import pytest

from core.chat_core.key_vault import EncryptedKey, KeyVault, KeyVaultError

OLD_KEY = bytes(range(32))
NEW_KEY = bytes(range(32, 64))
SECRET = "sk-ant-test-secret-value"


def test_round_trips_an_api_key():
    vault = KeyVault([OLD_KEY])

    sealed = vault.encrypt("user-1", "anthropic", SECRET)

    assert SECRET.encode() not in sealed.ciphertext
    assert vault.decrypt("user-1", "anthropic", sealed) == SECRET


def test_ciphertext_copied_to_another_user_or_provider_does_not_open():
    vault = KeyVault([OLD_KEY])
    sealed = vault.encrypt("user-1", "anthropic", SECRET)

    with pytest.raises(KeyVaultError):
        vault.decrypt("user-2", "anthropic", sealed)
    with pytest.raises(KeyVaultError):
        vault.decrypt("user-1", "openrouter", sealed)


def test_tampered_ciphertext_does_not_open():
    vault = KeyVault([OLD_KEY])
    sealed = vault.encrypt("user-1", "anthropic", SECRET)
    flipped = bytes([sealed.ciphertext[0] ^ 1]) + sealed.ciphertext[1:]

    with pytest.raises(KeyVaultError):
        vault.decrypt("user-1", "anthropic", EncryptedKey(flipped, sealed.nonce, sealed.key_version))


def test_rows_sealed_by_an_old_key_still_open_after_rotation():
    before_rotation = KeyVault([OLD_KEY])
    sealed = before_rotation.encrypt("user-1", "anthropic", SECRET)

    after_rotation = KeyVault([NEW_KEY, OLD_KEY])

    assert after_rotation.decrypt("user-1", "anthropic", sealed) == SECRET


def test_new_writes_use_the_newest_key():
    vault = KeyVault([NEW_KEY, OLD_KEY])

    sealed = vault.encrypt("user-1", "anthropic", SECRET)

    assert sealed.key_version == KeyVault([NEW_KEY]).encrypt("user-1", "anthropic", SECRET).key_version


def test_row_sealed_by_a_removed_key_cannot_be_opened():
    sealed = KeyVault([OLD_KEY]).encrypt("user-1", "anthropic", SECRET)

    with pytest.raises(KeyVaultError):
        KeyVault([NEW_KEY]).decrypt("user-1", "anthropic", sealed)


def test_repr_never_shows_key_material():
    vault = KeyVault([OLD_KEY])

    assert base64.b64encode(OLD_KEY).decode() not in repr(vault)
    assert OLD_KEY.hex() not in repr(vault)


def test_from_env_reads_comma_separated_keys(monkeypatch):
    encoded_new = base64.b64encode(NEW_KEY).decode()
    encoded_old = base64.b64encode(OLD_KEY).decode()
    monkeypatch.setenv("KEY_ENCRYPTION_KEYS", f"{encoded_new}, {encoded_old}")

    sealed = KeyVault.from_env().encrypt("user-1", "anthropic", SECRET)

    assert KeyVault([NEW_KEY]).decrypt("user-1", "anthropic", sealed) == SECRET


def test_from_env_requires_keys(monkeypatch):
    monkeypatch.delenv("KEY_ENCRYPTION_KEYS", raising=False)

    with pytest.raises(RuntimeError, match="KEY_ENCRYPTION_KEYS is required"):
        KeyVault.from_env()


def test_from_env_rejects_keys_of_the_wrong_length(monkeypatch):
    monkeypatch.setenv("KEY_ENCRYPTION_KEYS", base64.b64encode(os.urandom(16)).decode())

    with pytest.raises(RuntimeError, match="32 bytes"):
        KeyVault.from_env()
