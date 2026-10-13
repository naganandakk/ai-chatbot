from abc import ABC, abstractmethod
from dataclasses import dataclass

from .key_vault import EncryptedKey


@dataclass(frozen=True)
class User:
    id: str
    google_sub: str
    email: str
    name: str
    picture: str


@dataclass(frozen=True)
class RefreshToken:
    user_id: str
    expires_at: str
    revoked: bool


@dataclass(frozen=True)
class AuditEvent:
    # Records who changed a provider key, and when. It never holds the key itself.
    id: str
    user_id: str
    action: str
    provider: str
    created_at: str


@dataclass(frozen=True)
class ApiKeyRecord:
    provider: str
    last4: str
    updated_at: str
    sealed: EncryptedKey


class AccountStore(ABC):
    """Persistence for users, their refresh tokens, and their provider API keys.

    Refresh tokens are stored only as hashes. API keys are stored only as encrypted
    values (see KeyVault), and callers never read a plaintext key back from here.
    """

    @abstractmethod
    def upsert_user(self, google_sub: str, email: str, name: str, picture: str) -> User:
        ...

    @abstractmethod
    def get_user(self, user_id: str) -> User | None:
        ...

    @abstractmethod
    def count_users(self) -> int:
        ...

    @abstractmethod
    def get_active_provider(self, user_id: str) -> str | None:
        # The provider the user chose to chat with. None until they choose one.
        ...

    @abstractmethod
    def set_active_provider(self, user_id: str, provider: str | None) -> None:
        ...

    @abstractmethod
    def claim_unowned_sessions(self, user_id: str) -> None:
        # Sessions created before accounts existed have no owner. The first user to sign in
        # takes them over.
        ...

    @abstractmethod
    def save_refresh_token(self, token_hash: str, user_id: str, expires_at: str) -> None:
        ...

    @abstractmethod
    def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        ...

    @abstractmethod
    def revoke_refresh_token(self, token_hash: str) -> None:
        ...

    @abstractmethod
    def revoke_user_refresh_tokens(self, user_id: str) -> None:
        ...

    @abstractmethod
    def save_api_key(self, user_id: str, provider: str, sealed: EncryptedKey, last4: str) -> None:
        ...

    @abstractmethod
    def get_api_key(self, user_id: str, provider: str) -> ApiKeyRecord | None:
        ...

    @abstractmethod
    def list_api_keys(self, user_id: str) -> list[ApiKeyRecord]:
        ...

    @abstractmethod
    def list_all_api_keys(self) -> list[tuple[str, ApiKeyRecord]]:
        # Every saved key with its owner's user ID, for re-sealing after a key rotation
        ...

    @abstractmethod
    def replace_api_key_seal(
        self, user_id: str, provider: str, expected: EncryptedKey, sealed: EncryptedKey
    ) -> bool:
        # Swaps in a re-sealed value only while the row still holds `expected`, so a key the user
        # saved in the meantime is not overwritten. Returns False when the row did not match.
        ...

    @abstractmethod
    def delete_api_key(self, user_id: str, provider: str) -> None:
        # Deleting a key that is not there is not an error
        ...

    @abstractmethod
    def record_audit_event(self, user_id: str, action: str, provider: str) -> None:
        ...

    @abstractmethod
    def list_audit_events(self, user_id: str) -> list[AuditEvent]:
        # Oldest first
        ...
