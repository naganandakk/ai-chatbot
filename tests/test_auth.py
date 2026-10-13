from datetime import UTC, datetime, timedelta

from backend.app import create_app
from backend.app.auth import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    AuthConfig,
    GoogleIdentity,
    InvalidCredential,
    TokenService,
)
from core.chat_core.duckdb_store import DuckDBSessionStore
from core.chat_core.store import InMemorySessionStore
from tests.support import TEST_SECRET, USER_ID


class FakeVerifier:
    # Maps a credential string to the identity Google would have verified
    def __init__(self, identities: dict[str, GoogleIdentity]) -> None:
        self._identities = identities

    def verify(self, credential: str) -> GoogleIdentity:
        if credential not in self._identities:
            raise InvalidCredential("Wrong audience or bad signature")
        return self._identities[credential]


ADA = GoogleIdentity(sub="google-ada", email="ada@example.com", email_verified=True, name="Ada", picture="")
BO = GoogleIdentity(sub="google-bo", email="bo@other.org", email_verified=True, name="Bo", picture="")


def make_client(store=None, allowed_emails=frozenset(), allowed_domains=frozenset()):
    config = AuthConfig(
        tokens=TokenService(TEST_SECRET),
        verifier=FakeVerifier({"ada-token": ADA, "bo-token": BO}),
        allowed_emails=allowed_emails,
        allowed_domains=allowed_domains,
        cookie_secure=False,
    )
    app = create_app(store=store or InMemorySessionStore(), auth=config)
    return app.test_client()


def test_api_routes_require_a_signed_in_user():
    client = make_client()

    response = client.get("/api/sessions")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Sign in required"}


def test_health_stays_public():
    assert make_client().get("/api/health").status_code == 200


def test_expired_access_token_is_rejected():
    client = make_client()
    stale = TokenService(TEST_SECRET).issue_access_token(
        USER_ID,
        now=datetime.now(UTC) - timedelta(hours=1),
    )
    client.set_cookie(ACCESS_COOKIE, stale)

    assert client.get("/api/sessions").status_code == 401


def test_tampered_access_token_is_rejected():
    client = make_client()
    token = TokenService(TEST_SECRET).issue_access_token(USER_ID)
    client.set_cookie(ACCESS_COOKIE, token[:-2] + ("AA" if not token.endswith("AA") else "BB"))

    assert client.get("/api/sessions").status_code == 401


def test_token_signed_with_another_secret_is_rejected():
    client = make_client()
    forged = TokenService("another-secret-that-is-long-enough-to-pass").issue_access_token(USER_ID)
    client.set_cookie(ACCESS_COOKIE, forged)

    assert client.get("/api/sessions").status_code == 401


def test_google_sign_in_sets_cookies_and_identifies_the_user():
    client = make_client()

    response = client.post("/api/auth/google", json={"credential": "ada-token"})

    assert response.status_code == 200
    assert response.get_json()["email"] == "ada@example.com"
    assert client.get_cookie(ACCESS_COOKIE) is not None
    assert client.get_cookie(REFRESH_COOKIE, path="/api/auth") is not None
    assert client.get("/api/auth/me").get_json()["name"] == "Ada"
    assert client.get("/api/sessions").status_code == 200


def test_invalid_google_credential_is_rejected():
    client = make_client()

    response = client.post("/api/auth/google", json={"credential": "forged"})

    assert response.status_code == 401
    assert client.get_cookie(ACCESS_COOKIE) is None


def test_unverified_google_email_is_rejected():
    unverified = GoogleIdentity(sub="x", email="x@example.com", email_verified=False, name="", picture="")
    config = AuthConfig(
        tokens=TokenService(TEST_SECRET),
        verifier=FakeVerifier({"token": unverified}),
        cookie_secure=False,
    )
    client = create_app(store=InMemorySessionStore(), auth=config).test_client()

    assert client.post("/api/auth/google", json={"credential": "token"}).status_code == 403


def test_allowlists_restrict_who_can_sign_in():
    client = make_client(allowed_emails=frozenset({"ada@example.com"}), allowed_domains=frozenset({"allowed.org"}))

    assert client.post("/api/auth/google", json={"credential": "bo-token"}).status_code == 403
    assert client.post("/api/auth/google", json={"credential": "ada-token"}).status_code == 200


def test_first_sign_in_claims_sessions_from_before_accounts_existed(tmp_path):
    store = DuckDBSessionStore(str(tmp_path / "chat.duckdb"))
    legacy = store.create(USER_ID)
    store.connection.execute("UPDATE chat_sessions SET user_id = NULL WHERE id = ?", [legacy.id])
    client = make_client(store=store)

    client.post("/api/auth/google", json={"credential": "ada-token"})

    listed = client.get("/api/sessions").get_json()
    assert [session["id"] for session in listed] == [legacy.id]
    store.close()


def test_refresh_rotates_the_refresh_token():
    client = make_client()
    client.post("/api/auth/google", json={"credential": "ada-token"})
    first_refresh = client.get_cookie(REFRESH_COOKIE, path="/api/auth").value

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert client.get_cookie(REFRESH_COOKIE, path="/api/auth").value != first_refresh


def test_reusing_a_rotated_refresh_token_signs_the_user_out_everywhere():
    client = make_client()
    client.post("/api/auth/google", json={"credential": "ada-token"})
    old_refresh = client.get_cookie(REFRESH_COOKIE, path="/api/auth").value
    client.post("/api/auth/refresh")
    current_refresh = client.get_cookie(REFRESH_COOKIE, path="/api/auth").value

    # Someone replays the token that was already rotated away
    client.set_cookie(REFRESH_COOKIE, old_refresh, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401

    # The legitimate newer token no longer works either
    client.set_cookie(REFRESH_COOKIE, current_refresh, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_token_and_clears_cookies():
    client = make_client()
    client.post("/api/auth/google", json={"credential": "ada-token"})
    refresh = client.get_cookie(REFRESH_COOKIE, path="/api/auth").value

    assert client.post("/api/auth/logout").status_code == 200

    client.set_cookie(REFRESH_COOKIE, refresh, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_each_user_only_sees_their_own_sessions_through_the_api():
    store = InMemorySessionStore()
    ada_client = make_client(store=store)
    bo_client = make_client(store=store)
    ada_client.post("/api/auth/google", json={"credential": "ada-token"})
    bo_client.post("/api/auth/google", json={"credential": "bo-token"})

    created = ada_client.post("/api/sessions").get_json()

    assert bo_client.get(f"/api/sessions/{created['id']}").status_code == 404
    assert bo_client.get("/api/sessions").get_json() == []
    assert bo_client.delete(f"/api/sessions/{created['id']}").status_code == 404


def test_sign_in_attempts_are_rate_limited_with_a_json_error(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    client = make_client()

    statuses = [
        client.post("/api/auth/google", json={"credential": "forged"}).status_code
        for _ in range(11)
    ]

    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    limited = client.post("/api/auth/google", json={"credential": "forged"})
    assert limited.get_json()["error"].startswith("Too many requests")
