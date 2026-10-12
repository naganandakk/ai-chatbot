import json
import os
from urllib.parse import quote

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from core.chat_core.attachments import MB, AttachmentLimits, UploadedFile
from core.chat_core.models import summarize_usage
from core.chat_core.providers import (
    ProviderError,
    ReplyReset,
    TruncatedReplyError,
    create_provider_by_name,
)
from core.chat_core.service import ChatService
from core.chat_core.store import InMemorySessionStore, SessionStore


def create_app(
    store: SessionStore | None = None,
    chat_service: ChatService | None = None,
) -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    session_store = store or InMemorySessionStore()
    limits = AttachmentLimits.from_env()
    # Caps the whole request body, so an oversized upload is refused before it is read
    app.config["MAX_CONTENT_LENGTH"] = limits.max_request_bytes
    app.config["SESSION_STORE"] = session_store
    app.config["CHAT_SERVICE"] = chat_service or ChatService(
        store=session_store,
        attachment_limits=limits,
    )

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

    @app.get("/api/attachments/<attachment_id>")
    def get_attachment(attachment_id: str):
        try:
            attachment = session_store.get_attachment(attachment_id)
        except KeyError:
            return jsonify({"error": "Attachment not found"}), 404

        response = Response(attachment.data, mimetype=attachment.media_type)
        # Only images show inline. Other files download, so a PDF cannot run script on this origin.
        disposition = "inline" if attachment.media_type.startswith("image/") else "attachment"
        response.headers["Content-Disposition"] = (
            f"{disposition}; filename*=UTF-8''{quote(attachment.filename)}"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post("/api/sessions")
    def create_session():
        session = session_store.create()
        return jsonify(session.to_dict()), 201

    @app.get("/api/sessions")
    def list_sessions():
        sessions = [
            session.to_dict(include_messages=False)
            for session in session_store.list()
        ]
        return jsonify(sessions)

    @app.get("/api/sessions/<session_id>")
    def get_session(session_id: str):
        session = session_store.get(session_id)

        if session is None:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict())

    @app.delete("/api/sessions/<session_id>/messages")
    def clear_session(session_id: str):
        try:
            session = session_store.clear(session_id)
        except KeyError:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict())

    @app.delete("/api/sessions/<session_id>")
    def delete_session(session_id: str):
        try:
            session_store.delete(session_id)
        except KeyError:
            return jsonify({"error": "Session not found"}), 404

        return jsonify({"message": "Session deleted successfully"})

    @app.put("/api/sessions/<session_id>")
    def update_session(session_id: str):
        payload = request.get_json(silent=False) or {}
        title = payload.get("title", "New Chat")
        try:
            session = session_store.update(session_id, title)
        except KeyError:
            return jsonify({"error": "Session not found"}), 404

        return jsonify(session.to_dict(include_messages=False))

    # One provider per name, so each provider's HTTP client is reused across requests
    model_providers = {}

    @app.get("/api/models")
    def list_models():
        provider_name = request.args.get("provider") or os.getenv("AI_PROVIDER", "")
        provider_name = provider_name.strip().lower()

        try:
            if provider_name not in model_providers:
                model_providers[provider_name] = create_provider_by_name(provider_name)
            models = model_providers[provider_name].list_models()
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 400
        except ProviderError as error:
            return jsonify({"error": str(error)}), 502

        return jsonify({
            "provider": provider_name,
            "models": [{"id": model.id, "name": model.name} for model in models],
        })

    def session_state(session_id: str) -> dict | None:
        session = session_store.get(session_id)
        return session.to_dict() if session else None

    @app.post("/api/sessions/<session_id>/messages")
    def send_message(session_id: str):
        # JSON for text only. Multipart carries the prompt fields plus any files.
        if request.mimetype == "multipart/form-data":
            prompt = request.form.get("message", "")
            model = request.form.get("model")
            files = [
                UploadedFile(file.filename or "", file.read())
                for file in request.files.getlist("files")
            ]
        else:
            payload = request.get_json(silent=False) or {}
            prompt = payload.get("message", "")
            model = payload.get("model")
            files = []

        def generate():
            try:
                chunks = app.config["CHAT_SERVICE"].stream_reply(
                    session_id, prompt, model, files
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

                session = session_store.get(session_id)
                # The summary has no messages, so the session's usage totals are added to it
                summary = session.to_dict(include_messages=False)
                summary["usage"] = summarize_usage(session.messages).to_dict()
                event = {
                    "message": reply.to_dict(),
                    "session": summary,
                }
                yield f"event: done\ndata: {json.dumps(event)}\n\n"
            except (KeyError, ValueError, TruncatedReplyError) as error:
                event = {"message": str(error), "session": session_state(session_id)}
                yield f"event: error\ndata: {json.dumps(event)}\n\n"
            except Exception:
                app.logger.exception("Chat stream failed")
                event = {
                    "message": "The model could not respond. Please try again.",
                    "session": session_state(session_id),
                }
                yield f"event: error\ndata: {json.dumps(event)}\n\n"

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream",
        )

    return app