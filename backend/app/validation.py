from typing import Any

from flask import request

from backend.app.errors import ApiError


def json_object() -> dict[str, Any]:
    """The request's JSON body as a dict. A missing body counts as empty; anything else is refused."""
    payload = request.get_json(silent=False)

    if payload is None:
        return {}

    if not isinstance(payload, dict):
        raise ApiError(400, "Request body must be a JSON object")

    return payload


def optional_str(payload: dict[str, Any], name: str) -> str | None:
    value = payload.get(name)

    if value is None or isinstance(value, str):
        return value

    raise ApiError(400, f"{name} must be a string")


def required_text(payload: dict[str, Any], name: str, max_length: int) -> str:
    value = payload.get(name)

    if not isinstance(value, str):
        raise ApiError(400, f"{name} is required")

    value = value.strip()

    if not value:
        raise ApiError(400, f"{name} cannot be empty")

    if len(value) > max_length:
        raise ApiError(400, f"{name} must be at most {max_length} characters")

    return value


def string_list(payload: dict[str, Any], name: str) -> list[str]:
    value = payload.get(name) or []

    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ApiError(400, f"{name} must be a list of strings")

    return value
