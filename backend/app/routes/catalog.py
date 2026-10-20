from flask import Blueprint, current_app, g, jsonify, request

from backend.app.errors import ApiError
from core.chat_core.attachments import AttachmentLimits
from core.chat_core.providers import ProviderError
from core.chat_core.service import ApiKeyRequired
from core.chat_core.tools import TOOLS


def create_catalog_blueprint(limits: AttachmentLimits) -> Blueprint:
    """Read-only reference data: health, upload limits, tools and models."""
    bp = Blueprint("catalog", __name__, url_prefix="/api")

    @bp.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @bp.get("/attachment-limits")
    def attachment_limits():
        return jsonify(limits.to_dict())

    @bp.get("/tools")
    def list_tools():
        return jsonify([tool.to_dict() for tool in TOOLS])

    @bp.get("/models")
    def list_models():
        service = current_app.config["CHAT_SERVICE"]
        provider_name = service.provider_name_for(g.user_id, request.args.get("provider"))

        try:
            models = service.list_models(g.user_id, provider_name)
        except ApiKeyRequired as error:
            raise ApiError(409, str(error), code="api_key_required") from None
        except ValueError as error:
            raise ApiError(400, str(error)) from None
        except ProviderError as error:
            raise ApiError(502, str(error)) from None

        return jsonify({
            "provider": provider_name,
            "models": [{"id": model.id, "name": model.name} for model in models],
        })

    return bp
