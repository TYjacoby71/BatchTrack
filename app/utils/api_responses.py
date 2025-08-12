from flask import jsonify, request, Response
from typing import Any, Dict, Optional, Union, List
import json

class APIResponse:
    """Standardized API response handler"""

    @staticmethod
    def success(data: Any = None, message: str = "Success", status_code: int = 200) -> Response:
        """Standard success response"""
        response_data = {
            'success': True,
            'message': message,
            'data': data
        }
        return jsonify(response_data), status_code

    @staticmethod
    def error(message: str, errors: Optional[Dict] = None, status_code: int = 400) -> Response:
        """Standard error response"""
        response_data = {
            'success': False,
            'message': message,
            'errors': errors or {}
        }
        return jsonify(response_data), status_code

    @staticmethod
    def validation_error(errors: Dict[str, List[str]]) -> Response:
        """Validation error response"""
        return APIResponse.error(
            message="Validation failed",
            errors=errors,
            status_code=422
        )

    @staticmethod
    def not_found(resource: str = "Resource") -> Response:
        """404 error response"""
        return APIResponse.error(
            message=f"{resource} not found",
            status_code=404
        )

    @staticmethod
    def forbidden(message: str = "Access denied") -> Response:
        """403 error response"""
        return APIResponse.error(
            message=message,
            status_code=403
        )

    @staticmethod
    def handle_request_content():
        """Smart request content handling"""
        if request.is_json:
            return request.get_json()
        elif request.form:
            return request.form.to_dict()
        else:
            return {}

def api_route(methods=['GET']):
    """Decorator for API routes with consistent error handling"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                return APIResponse.validation_error({'general': [str(e)]})
            except PermissionError as e:
                return APIResponse.forbidden(str(e))
            except Exception as e:
                from flask import current_app
                current_app.logger.error(f"API error in {func.__name__}: {str(e)}")
                return APIResponse.error("Internal server error", status_code=500)

        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# Backwards compatibility functions
def api_error(message: str, status_code: int = 400, **kwargs) -> Response:
    """Legacy function - use APIResponse.error() instead"""
    return APIResponse.error(message, status_code=status_code, **kwargs)

def api_success(data: Any = None, message: str = "Success", **kwargs) -> Response:
    """Legacy function - use APIResponse.success() instead"""
    return APIResponse.success(data, message=message, **kwargs)

# Export APIResponse class for backwards compatibility
__all__ = ['APIResponse', 'api_response', 'api_error', 'api_success']