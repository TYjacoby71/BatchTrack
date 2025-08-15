from flask import request

def wants_json() -> bool:
    """Check if the request wants JSON response"""
    if request.path.startswith("/api/"):
        return True

    accept = request.accept_mimetypes
    return "application/json" in accept and not accept.accept_html