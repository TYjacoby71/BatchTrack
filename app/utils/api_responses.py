from __future__ import annotations

from functools import wraps
from typing import Any, Dict, List, Optional

from flask import Response, current_app, jsonify, request

__all__ = ["APIResponse", "api_route", "api_error", "api_success"]


class APIResponse:
    """Standardized API response helper."""

    @staticmethod
    def success(
        data: Any = None, message: str = "Success", status_code: int = 200
    ) -> Response:
        payload = {"success": True, "message": message, "data": data}
        return jsonify(payload), status_code

    @staticmethod
    def error(
        message: str, errors: Optional[Dict] = None, status_code: int = 400
    ) -> Response:
        payload = {"success": False, "message": message, "errors": errors or {}}
        return jsonify(payload), status_code

    @staticmethod
    def validation_error(errors: Dict[str, List[str]]) -> Response:
        return APIResponse.error("Validation failed", errors=errors, status_code=422)

    @staticmethod
    def not_found(resource: str = "Resource") -> Response:
        return APIResponse.error(f"{resource} not found", status_code=404)

    @staticmethod
    def forbidden(message: str = "Access denied") -> Response:
        return APIResponse.error(message, status_code=403)

    @staticmethod
    def handle_request_content() -> Dict[str, Any]:
        if request.is_json:
            return request.get_json() or {}
        if request.form:
            return request.form.to_dict()
        return {}


def api_error(
    message: str, status_code: int = 400, errors: Optional[Dict] = None
) -> Response:
    """Legacy helper function for API error responses."""
    return APIResponse.error(message, errors=errors, status_code=status_code)


def api_success(
    data: Any = None, message: str = "Success", status_code: int = 200
) -> Response:
    """Legacy helper function for API success responses."""
    return APIResponse.success(data=data, message=message, status_code=status_code)


def api_route(methods: Optional[List[str]] = None):
    """Decorator for API routes with consistent failure handling."""

    methods = methods or ["GET"]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as exc:
                return APIResponse.validation_error({"general": [str(exc)]})
            except PermissionError as exc:
                return APIResponse.forbidden(str(exc))
            except Exception as exc:  # pragma: no cover - defensive logging
                current_app.logger.exception("API error in %s: %s", func.__name__, exc)
                return APIResponse.error("Internal server error", status_code=500)

        wrapper.methods = methods  # type: ignore[attr-defined]
        return wrapper

    return decorator
