import json

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

from core.chat_core.providers import TruncatedReplyError
from core.chat_core.service import ChatService
from core.chat_core.store import InMemorySessionStore, SessionStore


def create_app(
    store: SessionStore | None = None,
    chat_service: ChatService | None = None,
) -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    session_store = store or InMemorySessionStore()
    app.config["SESSION_STORE"] = session_store
    app.config["CHAT_SERVICE"] = chat_service or ChatService(store=session_store)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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

    @app.post("/api/sessions/<session_id>/messages")
    def send_message(session_id: str):
        payload = request.get_json(silent=False) or {}
        prompt = payload.get("message", "")
        model = payload.get("model")

        def generate():
            try:
                for chunk in app.config["CHAT_SERVICE"].stream_reply(session_id, prompt, model):
                    event = json.dumps({"text": chunk})
                    yield f"event: delta\ndata: {event}\n\n"

                yield "event: done\ndata: {}\n\n"
            except (KeyError, ValueError, TruncatedReplyError) as error:
                event = json.dumps({"message": str(error)})
                yield f"event: error\ndata: {event}\n\n"
            except Exception:
                app.logger.exception("Chat stream failed")
                yield (
                    "event: error\n"
                    'data: {"message": "The model could not respond. Please try again."}\n\n'
                )

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream",
        )

    return app