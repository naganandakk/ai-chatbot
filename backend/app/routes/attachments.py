from urllib.parse import quote

from flask import Blueprint, Response, g

from backend.app.errors import ApiError
from core.chat_core.store import SessionStore


def create_attachments_blueprint(store: SessionStore) -> Blueprint:
    bp = Blueprint("attachments", __name__, url_prefix="/api/attachments")

    @bp.get("/<attachment_id>")
    def get_attachment(attachment_id: str):
        try:
            attachment = store.get_attachment(g.user_id, attachment_id)
        except KeyError:
            raise ApiError(404, "Attachment not found") from None

        response = Response(attachment.data, mimetype=attachment.media_type)
        # Only images show inline. Other files download, so a PDF cannot run script on this origin.
        disposition = "inline" if attachment.media_type.startswith("image/") else "attachment"
        response.headers["Content-Disposition"] = (
            f"{disposition}; filename*=UTF-8''{quote(attachment.filename)}"
        )
        # Uploaded files are untrusted, so even an image is sandboxed if opened directly
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response

    return bp
