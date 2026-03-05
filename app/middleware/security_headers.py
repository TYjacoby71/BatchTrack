"""Response security-header middleware utilities.

Synopsis:
Applies request-correlation and browser hardening headers to outgoing responses.

Glossary:
- HSTS: Strict-Transport-Security header for HTTPS-only browser behavior.
- CSP: Content-Security-Policy header controlling allowed resource sources.
"""

from __future__ import annotations

import logging

from flask import Response, request

logger = logging.getLogger(__name__)


def apply_security_headers(
    response: Response,
    *,
    app,
    request_id: str | None,
    disable_security_headers: bool,
    secure_env: bool,
    force_security_headers: bool,
    security_headers: dict[str, str],
) -> Response:
    if request_id:
        response.headers.setdefault("X-Request-ID", str(request_id))

    if disable_security_headers:
        return response

    if not (secure_env or force_security_headers):
        return response

    def _is_effectively_secure() -> bool:
        if request.is_secure:
            return True
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto:
            forwarded_values = {
                value.strip().lower() for value in forwarded_proto.split(",")
            }
            if "https" in forwarded_values:
                return True
        preferred_scheme = app.config.get("PREFERRED_URL_SCHEME", "http")
        return preferred_scheme == "https"

    enforce_hsts = force_security_headers or _is_effectively_secure()
    for header_name, header_value in security_headers.items():
        if not header_value:
            continue
        if header_name.lower() == "strict-transport-security" and not enforce_hsts:
            continue
        response.headers.setdefault(header_name, header_value)
    return response
