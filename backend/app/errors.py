from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from core.chat_core.attachments import MB, AttachmentLimits


class ApiError(Exception):
    """Raised by route code to answer with the standard `{error, code?}` body."""

    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


def error_body(message: str, code: str | None = None) -> dict[str, str]:
    body = {"error": message}
    if code:
        body["code"] = code
    return body


def register_error_handlers(app: Flask, limits: AttachmentLimits) -> None:
    # Every error answers with JSON, so the client never has to guess the body's format

    @app.errorhandler(ApiError)
    def api_error(error: ApiError):
        return jsonify(error_body(error.message, error.code)), error.status

    @app.errorhandler(429)
    def rate_limited(_error):
        return jsonify(error_body("Too many requests. Please wait a moment and try again.")), 429

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(error_body(
            "The message is too large. Attachments in one message can total at most "
            f"{limits.max_total_bytes // MB} MB."
        )), 413

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        return jsonify(error_body(error.description or error.name)), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        app.logger.exception("Unhandled error", exc_info=error)
        return jsonify(error_body("Something went wrong. Please try again.")), 500
