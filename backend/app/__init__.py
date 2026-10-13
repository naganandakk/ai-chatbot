import json
import os
from urllib.parse import quote

from flask import Flask, Response, g, jsonify, request, stream_with_context
from flask_limiter import Limiter
from werkzeug.exceptions import RequestEntityTooLarge

from backend.app.api_keys import register_api_key_routes
from backend.app.auth import AuthConfig, caller_key, install_auth
from core.chat_core.attachments import MB, AttachmentLimits, UploadedFile
from core.chat_core.key_vault import KeyVault
from core.chat_core.models import summarize_usage
from core.chat_core.providers import (
    ProviderError,
    ReplyReset,
    TruncatedReplyError,
)
from core.chat_core.service import ApiKeyRequired, ChatService
from core.chat_core.store import InMemorySessionStore, SessionStore
from core.chat_core.tools import TOOLS


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
    install_auth(app, auth or AuthConfig.from_env(), session_store, limiter)
    register_api_key_routes(app, session_store, vault, app.config["CHAT_SERVICE"], limiter)

    @app.after_request
    def security_headers(response):
        # The API returns JSON and streams, never HTML, so nothing it sends may run as a page.
        # HSTS is set by the HTTPS proxy in front of the app, since Flask cannot see the scheme.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if request.path.startswith("/api/"):
            # Session, key-status and chat responses must not be kept by browsers or caches
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(429)
    def rate_limited(_error):
        return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify({
            "error": (
                "The message is too large. Attachments in one message can total at most "
                f"{limits.max_total_bytes // MB} MB."
            ),
        }), 413

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/attachment-limits")
    def attachment_limits():
        return jsonify(limits.to_dict())

    @app.get("/api/tools")
    def list_tools():
        return jsonify([tool.to_dict() for tool in TOOLS])

    @app.get("/api/attachments/<attachment_id>")
    def get_attachment(attachment_id: str):
        try:
            attachment = session_store.get_attachment(g.user_id, attachment_id)
        except KeyError:
            return jsonify({"error": "Attachment not found"}), 404

        response = Response(attachment.data, mimetype=attachment.media_type)
        # Only images show inline. Other files download, so a PDF cannot run script on this origin.
        disposition = "inline" if attachment.media_type.startswith("image/") else "attachment"
        response.headers["Content-Disposition"] = (
            f"{disposition}; filename*=UTF-8''{quote(attachment.filename)}"
        )
        # Uploaded files are untrusted, so even an image is sandboxed if opened directly
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response

    @app.post("/api/sessions")
    def create_session():
        session = session_store.create(g.user_id)
        return jsonify(session.to_dict()), 201

    @app.get("/api/sessions")
    def list_sessions():
        sessions = [
            session.to_dict(include_messages=False)
            for session in session_store.list(g.user_id)
        ]
        return jsonify(sessions)

    @app.get("/api/sessions/<session_id>")
    def get_session(session_id: str):
        session = session_store.get(g.user_id, session_id)

        if session is None:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict())

    @app.delete("/api/sessions/<session_id>/messages")
    def clear_session(session_id: str):
        try:
            session = session_store.clear(g.user_id, session_id)
        except KeyError:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict())

    @app.delete("/api/sessions/<session_id>")
    def delete_session(session_id: str):
        try:
            session_store.delete(g.user_id, session_id)
        except KeyError:
            return jsonify({"error": "Session not found"}), 404

        return jsonify({"message": "Session deleted successfully"})

    @app.put("/api/sessions/<session_id>")
    def update_session(session_id: str):
        payload = request.get_json(silent=False) or {}
        title = payload.get("title", "New Chat")
        try:
            session = session_store.update(g.user_id, session_id, title)
        except KeyError:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict(include_messages=False))

    @app.get("/api/models")
    def list_models():
        service = app.config["CHAT_SERVICE"]
        provider_name = service.provider_name_for(g.user_id, request.args.get("provider"))

        try:
            models = service.list_models(g.user_id, provider_name)
        except ApiKeyRequired as error:
            return jsonify({"error": str(error), "code": "api_key_required"}), 409
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderError as error:
            return jsonify({"error": str(error)}), 502

        return jsonify({
            "provider": provider_name,
            "models": [{"id": model.id, "name": model.name} for model in models],
        })

    @app.post("/api/sessions/<session_id>/messages")
    @limiter.limit("20 per minute")
    def send_message(session_id: str):
        # Read before the generator runs: the stream outlives the request handler's locals
        user_id = g.user_id

        # JSON for text only. Multipart carries the prompt fields plus any files.
        if request.mimetype == "multipart/form-data":
            prompt = request.form.get("message", "")
            model = request.form.get("model")
            provider_name = request.form.get("provider")
            tools = request.form.getlist("tools")
            files = [
                UploadedFile(file.filename or "", file.read())
                for file in request.files.getlist("files")
            ]
        else:
            payload = request.get_json(silent=False) or {}
            prompt = payload.get("message", "")
            model = payload.get("model")
            provider_name = payload.get("provider")
            tools = payload.get("tools") or []
            files = []

        def session_state() -> dict | None:
            session = session_store.get(user_id, session_id)
            return session.to_dict() if session else None

        def generate():
            try:
                chunks = app.config["CHAT_SERVICE"].stream_reply(
                    user_id, session_id, prompt, model, files, provider_name, tools=tools
                )
                while True:
                    try:
                        chunk = next(chunks)
                    except StopIteration as finished:
                        reply = finished.value
                        break

                    if isinstance(chunk, ReplyReset):
                        yield "event: reset\ndata: {}\n\n"
                    else:
                        event = json.dumps({"text": chunk})
                        yield f"event: delta\ndata: {event}\n\n"

                session = session_store.get(user_id, session_id)
                # The summary has no messages, so the session's usage totals are added to it
                summary = session.to_dict(include_messages=False)
                summary["usage"] = summarize_usage(session.messages).to_dict()
                event = {
                    "message": reply.to_dict(),
                    "session": summary,
                }
                yield f"event: done\ndata: {json.dumps(event)}\n\n"
            except ApiKeyRequired as error:
                event = {
                    "message": str(error),
                    "code": "api_key_required",
                    "session": session_state(),
                }
                yield f"event: error\ndata: {json.dumps(event)}\n\n"
            except (KeyError, ValueError, TruncatedReplyError) as error:
                event = {"message": str(error), "session": session_state()}
                yield f"event: error\ndata: {json.dumps(event)}\n\n"
            except Exception:
                app.logger.exception("Chat stream failed")
                event = {
                    "message": "The model could not respond. Please try again.",
                    "session": session_state(),
                }
                yield f"event: error\ndata: {json.dumps(event)}\n\n"

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream",
        )

    return app
