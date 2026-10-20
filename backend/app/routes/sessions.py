from flask import Blueprint, Response, current_app, g, jsonify, request, stream_with_context
from flask_limiter import Limiter

from backend.app.errors import ApiError
from backend.app.sse import format_event
from backend.app.validation import json_object, optional_str, required_text, string_list
from core.chat_core.attachments import UploadedFile
from core.chat_core.models import summarize_usage
from core.chat_core.providers import ReplyReset, TruncatedReplyError
from core.chat_core.service import ApiKeyRequired
from core.chat_core.store import SessionStore

MAX_TITLE_LENGTH = 200
SESSION_NOT_FOUND = "Session not found"


def create_sessions_blueprint(store: SessionStore, limiter: Limiter) -> Blueprint:
    bp = Blueprint("sessions", __name__, url_prefix="/api/sessions")

    @bp.post("")
    def create_session():
        session = store.create(g.user_id)
        return jsonify(session.to_dict()), 201

    @bp.get("")
    def list_sessions():
        sessions = [
            session.to_dict(include_messages=False)
            for session in store.list(g.user_id)
        ]
        return jsonify(sessions)

    @bp.get("/<session_id>")
    def get_session(session_id: str):
        session = store.get(g.user_id, session_id)

        if session is None:
            raise ApiError(404, SESSION_NOT_FOUND)

        return jsonify(session.to_dict())

    @bp.put("/<session_id>")
    def update_session(session_id: str):
        title = required_text(json_object(), "title", MAX_TITLE_LENGTH)

        try:
            session = store.update(g.user_id, session_id, title)
        except KeyError:
            raise ApiError(404, SESSION_NOT_FOUND) from None

        return jsonify(session.to_dict(include_messages=False))

    @bp.delete("/<session_id>/messages")
    def clear_session(session_id: str):
        try:
            session = store.clear(g.user_id, session_id)
        except KeyError:
            raise ApiError(404, SESSION_NOT_FOUND) from None

        return jsonify(session.to_dict())

    @bp.delete("/<session_id>")
    def delete_session(session_id: str):
        try:
            store.delete(g.user_id, session_id)
        except KeyError:
            raise ApiError(404, SESSION_NOT_FOUND) from None

        return jsonify({"message": "Session deleted successfully"})

    @bp.post("/<session_id>/messages")
    @limiter.limit("20 per minute")
    def send_message(session_id: str):
        # Read before the generator runs: the stream outlives the request handler's locals
        user_id = g.user_id
        service = current_app.config["CHAT_SERVICE"]
        logger = current_app.logger

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
            payload = json_object()
            prompt = optional_str(payload, "message") or ""
            model = optional_str(payload, "model")
            provider_name = optional_str(payload, "provider")
            tools = string_list(payload, "tools")
            files = []

        def session_state() -> dict | None:
            session = store.get(user_id, session_id)
            return session.to_dict() if session else None

        def generate():
            try:
                chunks = service.stream_reply(
                    user_id, session_id, prompt, model, files, provider_name, tools=tools
                )
                while True:
                    try:
                        chunk = next(chunks)
                    except StopIteration as finished:
                        reply = finished.value
                        break

                    if isinstance(chunk, ReplyReset):
                        yield format_event("reset", {})
                    else:
                        yield format_event("delta", {"text": chunk})

                session = store.get(user_id, session_id)
                # The summary has no messages, so the session's usage totals are added to it
                summary = session.to_dict(include_messages=False)
                summary["usage"] = summarize_usage(session.messages).to_dict()
                yield format_event("done", {"message": reply.to_dict(), "session": summary})
            except ApiKeyRequired as error:
                yield format_event("error", {
                    "message": str(error),
                    "code": "api_key_required",
                    "session": session_state(),
                })
            except (KeyError, ValueError, TruncatedReplyError) as error:
                yield format_event("error", {"message": str(error), "session": session_state()})
            except Exception:
                logger.exception("Chat stream failed")
                yield format_event("error", {
                    "message": "The model could not respond. Please try again.",
                    "session": session_state(),
                })

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream",
        )

    return bp
