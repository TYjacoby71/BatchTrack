from __future__ import annotations

from typing import Optional

from flask import Request, has_request_context, request

__all__ = ["wants_json"]

JSON_MIMETYPE = "application/json"
HTML_MIMETYPE = "text/html"


def wants_json(req: Optional[Request] = None) -> bool:
    """
    Determine whether the active request favors a JSON response.

    - API routes (`/api/...`) always return JSON.
    - Otherwise compare the accepted mimetypes, falling back gracefully when no
      request context exists (e.g., CLI scripts calling helpers directly).
    """
    req = req or (request if has_request_context() else None)
    if req is None:
        return False

    if req.path.startswith("/api/"):
        return True

    accept = getattr(req, "accept_mimetypes", None)
    if not accept:
        return False

    # Prefer the explicit best match when available.
    best = accept.best
    if best == JSON_MIMETYPE:
        return True

    return accept[JSON_MIMETYPE] > accept[HTML_MIMETYPE]