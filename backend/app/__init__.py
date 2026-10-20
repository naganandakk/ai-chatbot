import os

from flask import Flask
from flask_limiter import Limiter

from backend.app.api_keys import register_api_key_routes
from backend.app.auth import AuthConfig, caller_key, install_auth
from backend.app.errors import register_error_handlers
from backend.app.headers import register_security_headers
from backend.app.routes.attachments import create_attachments_blueprint
from backend.app.routes.catalog import create_catalog_blueprint
from backend.app.routes.sessions import create_sessions_blueprint
from core.chat_core.attachments import AttachmentLimits
from core.chat_core.key_vault import KeyVault
from core.chat_core.service import ChatService
from core.chat_core.store import InMemorySessionStore, SessionStore


def create_app(
    store: SessionStore | None = None,
    chat_service: ChatService | None = None,
    auth: AuthConfig | None = None,
    key_vault: KeyVault | None = None,
) -> Flask:
    app = Flask(__name__)

    session_store = store or InMemorySessionStore()
    limits = AttachmentLimits.from_env()
    vault = key_vault or KeyVault.from_env()
    # Caps the whole request body, so an oversized upload is refused before it is read
    app.config["MAX_CONTENT_LENGTH"] = limits.max_request_bytes
    app.config["SESSION_STORE"] = session_store
    # The store also keeps accounts, so one object serves sessions, sign-in and saved keys
    app.config["CHAT_SERVICE"] = chat_service or ChatService(
        store=session_store,
        attachment_limits=limits,
        accounts=session_store,
        key_vault=vault,
    )
    limiter = Limiter(
        caller_key,
        app=app,
        storage_uri="memory://",
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() != "false",
    )
    # Flask-Limiter holds the limiter weakly, so the app keeps the only strong reference
    app.config["LIMITER"] = limiter

    register_error_handlers(app, limits)
    register_security_headers(app)
    install_auth(app, auth or AuthConfig.from_env(), session_store, limiter)
    register_api_key_routes(app, session_store, vault, app.config["CHAT_SERVICE"], limiter)

    app.register_blueprint(create_catalog_blueprint(limits))
    app.register_blueprint(create_attachments_blueprint(session_store))
    app.register_blueprint(create_sessions_blueprint(session_store, limiter))

    return app
