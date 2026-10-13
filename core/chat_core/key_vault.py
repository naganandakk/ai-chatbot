import base64
import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_BYTES = 32


class KeyVaultError(Exception):
    pass


@dataclass(frozen=True)
class EncryptedKey:
    ciphertext: bytes
    nonce: bytes
    key_version: str


def key_version(master_key: bytes) -> str:
    # A fingerprint, so rows record which master key sealed them without exposing the key
    return hashlib.sha256(master_key).hexdigest()[:12]


class KeyVault:
    """Encrypts users' provider API keys before they are stored.

    The first master key seals new keys. Older keys stay in the list so rows sealed before a
    rotation can still be opened. Each ciphertext is bound to its owner and provider as
    associated data, so a value copied to another user's row will not decrypt.
    """

    def __init__(self, master_keys: Sequence[bytes]) -> None:
        if not master_keys:
            raise RuntimeError("At least one key encryption key is required")

        for master_key in master_keys:
            if len(master_key) != KEY_BYTES:
                raise RuntimeError(f"Key encryption keys must be {KEY_BYTES} bytes")

        self._ciphers = {key_version(key): AESGCM(key) for key in master_keys}
        self._current_version = key_version(master_keys[0])

    @property
    def current_version(self) -> str:
        return self._current_version

    @classmethod
    def from_env(cls) -> "KeyVault":
        # Comma-separated base64 keys, newest first
        raw = os.getenv("KEY_ENCRYPTION_KEYS", "").strip()
        encoded_keys = [item.strip() for item in raw.split(",") if item.strip()]

        if not encoded_keys:
            raise RuntimeError("KEY_ENCRYPTION_KEYS is required for the web app")

        try:
            master_keys = [base64.b64decode(item, validate=True) for item in encoded_keys]
        except ValueError:
            raise RuntimeError("KEY_ENCRYPTION_KEYS must contain base64 encoded keys") from None

        return cls(master_keys)

    def encrypt(self, user_id: str, provider: str, api_key: str) -> EncryptedKey:
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = self._ciphers[self._current_version].encrypt(
            nonce,
            api_key.encode(),
            _associated_data(user_id, provider),
        )
        return EncryptedKey(ciphertext=ciphertext, nonce=nonce, key_version=self._current_version)

    def decrypt(self, user_id: str, provider: str, sealed: EncryptedKey) -> str:
        cipher = self._ciphers.get(sealed.key_version)
        if cipher is None:
            raise KeyVaultError("Stored API key was sealed with an unknown key")

        try:
            plaintext = cipher.decrypt(
                sealed.nonce,
                sealed.ciphertext,
                _associated_data(user_id, provider),
            )
        except InvalidTag:
            raise KeyVaultError("Stored API key could not be opened") from None

        return plaintext.decode()

    def reseal(self, user_id: str, provider: str, sealed: EncryptedKey) -> EncryptedKey:
        # Moves a row sealed by an older master key onto the current one. Rows already on the
        # current key are returned unchanged.
        if sealed.key_version == self._current_version:
            return sealed

        return self.encrypt(user_id, provider, self.decrypt(user_id, provider, sealed))

    def __repr__(self) -> str:
        # Never show key material, even in debugging output
        return f"KeyVault(versions={sorted(self._ciphers)})"


def _associated_data(user_id: str, provider: str) -> bytes:
    return f"{user_id}|{provider}".encode()
