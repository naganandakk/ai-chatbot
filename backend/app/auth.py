import hashlib
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

import jwt
from flask import Flask, Response, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from core.chat_core.accounts import AccountStore, User

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
# The refresh cookie is sent only to the auth routes that use it
REFRESH_PATH = "/api/auth"
ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32

# Only these paths work without a signed-in user. Everything else under /api is protected,
# so a route added later is protected by default.
PUBLIC_PATHS = {"/api/health", "/api/auth/google", "/api/auth/refresh", "/api/auth/logout"}


class InvalidToken(Exception):
    pass


class InvalidCredential(Exception):
    pass


class TokenService:
    """Issues and checks the short-lived access JWT that identifies the caller."""

    def __init__(self, secret: str, access_ttl: timedelta = ACCESS_TTL) -> None:
        if len(secret) < MIN_SECRET_LENGTH:
            raise RuntimeError(f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters")

        self._secret = secret
        self._access_ttl = access_ttl

    @classmethod
    def from_env(cls) -> "TokenService":
        secret = os.getenv("JWT_SECRET", "").strip()

        if not secret:
            raise RuntimeError("JWT_SECRET is required for the web app")

        return cls(secret)

    def issue_access_token(self, user_id: str, now: datetime | None = None) -> str:
        issued_at = now or datetime.now(UTC)
        claims = {
            "sub": user_id,
            "iat": issued_at,
            "exp": issued_at + self._access_ttl,
        }
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM)

    def user_id_from_access_token(self, token: str) -> str:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={"require": ["sub", "iat", "exp"]},
            )
        except jwt.PyJWTError as error:
            raise InvalidToken(str(error)) from None

        return claims["sub"]


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str
    picture: str


class IdentityVerifier(Protocol):
    def verify(self, credential: str) -> GoogleIdentity:
        ...


class GoogleIdentityVerifier:
    """Checks a Google ID token's signature, audience, and expiry."""

    def __init__(self, client_id: str) -> None:
        self._client_id = client_id
        self._request = google_requests.Request()

    def verify(self, credential: str) -> GoogleIdentity:
        try:
            claims = id_token.verify_oauth2_token(credential, self._request, self._client_id)
        except ValueError as error:
            raise InvalidCredential(str(error)) from None

        return GoogleIdentity(
            sub=claims["sub"],
            email=claims.get("email", ""),
            email_verified=bool(claims.get("email_verified")),
            name=claims.get("name", ""),
            picture=claims.get("picture", ""),
        )


@dataclass(frozen=True)
class AuthConfig:
    tokens: TokenService
    verifier: IdentityVerifier
    # Empty allowlists mean any verified Google account may sign in
    allowed_emails: frozenset[str] = field(default_factory=frozenset)
    allowed_domains: frozenset[str] = field(default_factory=frozenset)
    cookie_secure: bool = True

    def allows(self, email: str) -> bool:
        if not self.allowed_emails and not self.allowed_domains:
            return True

        normalized = email.lower()
        domain = normalized.rpartition("@")[2]
        return normalized in self.allowed_emails or domain in self.allowed_domains

    @classmethod
    def from_env(cls) -> "AuthConfig":
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()

        if not client_id:
            raise RuntimeError("GOOGLE_CLIENT_ID is required for the web app")

        return cls(
            tokens=TokenService.from_env(),
            verifier=GoogleIdentityVerifier(client_id),
            allowed_emails=_csv_from_env("ALLOWED_EMAILS"),
            allowed_domains=_csv_from_env("ALLOWED_EMAIL_DOMAINS"),
            cookie_secure=os.getenv("COOKIE_SECURE", "true").strip().lower() != "false",
        )


def caller_key() -> str:
    # Signed-in calls share a budget per user. Anonymous calls (sign-in, refresh) per address.
    user_id = getattr(g, "user_id", None)
    return f"user:{user_id}" if user_id else f"ip:{get_remote_address()}"


def install_auth(app: Flask, config: AuthConfig, accounts: AccountStore, limiter: Limiter) -> None:
    @app.before_request
    def require_signed_in():
        if not request.path.startswith("/api/") or request.path in PUBLIC_PATHS:
            return None

        try:
            g.user_id = config.tokens.user_id_from_access_token(
                request.cookies.get(ACCESS_COOKIE, "")
            )
        except InvalidToken:
            return _unauthorized()

        return None

    @app.post("/api/auth/google")
    @limiter.limit("10 per minute")
    def sign_in_with_google():
        credential = (request.get_json(silent=True) or {}).get("credential", "")

        try:
            identity = config.verifier.verify(credential)
        except InvalidCredential:
            return jsonify({"error": "Google sign-in could not be verified"}), 401

        if not identity.email_verified or not config.allows(identity.email):
            return jsonify({"error": "This Google account is not allowed to use the app"}), 403

        is_first_user = accounts.count_users() == 0
        user = accounts.upsert_user(identity.sub, identity.email, identity.name, identity.picture)

        if is_first_user:
            # Chats from before accounts existed belong to whoever signs in first
            accounts.claim_unowned_sessions(user.id)

        response = jsonify(_user_json(user))
        _start_session(response, config, accounts, user.id)
        return response

    @app.post("/api/auth/refresh")
    @limiter.limit("30 per minute")
    def refresh_session():
        raw_token = request.cookies.get(REFRESH_COOKIE, "")
        record = accounts.get_refresh_token(_hash(raw_token)) if raw_token else None

        if record is None or _expired(record.expires_at):
            return _signed_out()

        if record.revoked:
            # A token that was already rotated is back in use, so it was probably copied.
            # End every session for this user.
            accounts.revoke_user_refresh_tokens(record.user_id)
            return _signed_out()

        user = accounts.get_user(record.user_id)
        if user is None:
            return _signed_out()

        accounts.revoke_refresh_token(_hash(raw_token))
        response = jsonify(_user_json(user))
        _start_session(response, config, accounts, user.id)
        return response

    @app.post("/api/auth/logout")
    def sign_out():
        raw_token = request.cookies.get(REFRESH_COOKIE, "")
        if raw_token:
            accounts.revoke_refresh_token(_hash(raw_token))

        response = jsonify({"message": "Signed out"})
        _clear_session(response, config)
        return response

    @app.get("/api/auth/me")
    def current_user():
        user = accounts.get_user(g.user_id)

        if user is None:
            return _unauthorized()

        return jsonify(_user_json(user))


def _start_session(response: Response, config: AuthConfig, accounts: AccountStore, user_id: str):
    refresh_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + REFRESH_TTL
    accounts.save_refresh_token(_hash(refresh_token), user_id, expires_at.isoformat())

    response.set_cookie(
        ACCESS_COOKIE,
        config.tokens.issue_access_token(user_id),
        max_age=int(ACCESS_TTL.total_seconds()),
        httponly=True,
        secure=config.cookie_secure,
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        secure=config.cookie_secure,
        samesite="Lax",
        path=REFRESH_PATH,
    )


def _clear_session(response: Response, config: AuthConfig) -> None:
    response.delete_cookie(
        ACCESS_COOKIE, path="/", secure=config.cookie_secure, httponly=True, samesite="Lax"
    )
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_PATH,
        secure=config.cookie_secure,
        httponly=True,
        samesite="Lax",
    )


def _unauthorized():
    response = jsonify({"error": "Sign in required"})
    response.status_code = 401
    return response


def _signed_out():
    # Used when the refresh token itself is dead, so the cookies go too
    response = _unauthorized()
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return response


def _user_json(user: User) -> dict[str, str]:
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}


def _hash(raw_token: str) -> str:
    # Refresh tokens are stored only as hashes, so a leaked table cannot be replayed
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _expired(expires_at: str) -> bool:
    return datetime.fromisoformat(expires_at) <= datetime.now(UTC)


def _csv_from_env(name: str) -> frozenset[str]:
    return frozenset(
        item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip()
    )
