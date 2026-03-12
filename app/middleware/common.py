"""Shared middleware utilities and constants.

Synopsis:
Holds reusable config/request helpers so guard modules stay focused.

Glossary:
- Request ID: Correlation identifier propagated through request/response headers.
- Permission scope: Route classification indicating developer/customer access intent.
- Security headers: Browser hardening headers applied on responses.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping

from flask import current_app, has_app_context, request

from ..route_access import RouteAccessConfig
from ..utils.permissions import PermissionScope, resolve_permission_scope

logger = logging.getLogger(__name__)

REQUEST_ID_MAX_LENGTH = 128
REQUEST_ID_ALLOWED_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")

DEFAULT_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com https://challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https://api.stripe.com https://challenges.cloudflare.com; "
        "frame-src https://js.stripe.com https://challenges.cloudflare.com; "
        "object-src 'none'"
    ),
}


def config_flag(name: str, default: bool = False, *, app=None) -> bool:
    if app is None and has_app_context():
        app = current_app._get_current_object()
    value = app.config.get(name, default) if app is not None else default
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def config_int(name: str, default: int, *, app=None) -> int:
    if app is None and has_app_context():
        app = current_app._get_current_object()
    raw = app.config.get(name, default) if app is not None else default
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid value for %s=%r; defaulting to %s", name, raw, default)
        return default


def config_str(name: str, default: str = "", *, app=None) -> str:
    if app is None and has_app_context():
        app = current_app._get_current_object()
    raw = app.config.get(name, default) if app is not None else default
    if raw is None:
        return default
    value = str(raw).strip()
    return value if value else default


def config_csv(name: str, default: str, *, app=None) -> tuple[str, ...]:
    value = config_str(name, default, app=app)
    parsed = tuple(part.strip() for part in value.split(",") if part.strip())
    if parsed:
        return parsed
    return tuple(part.strip() for part in default.split(",") if part.strip())


def path_matches_rule(path: str, rule: str) -> bool:
    if not rule:
        return False
    if rule.endswith("*"):
        return path.startswith(rule[:-1])
    return path == rule


def wants_json_response() -> bool:
    accepts = request.accept_mimetypes
    return request.path.startswith("/api/") or (
        "application/json" in accepts and not accepts.accept_html
    )


def normalize_request_id(raw: str | None) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    if len(value) > REQUEST_ID_MAX_LENGTH:
        value = value[:REQUEST_ID_MAX_LENGTH]
    if not REQUEST_ID_ALLOWED_RE.match(value):
        return None
    return value


def request_id_from_traceparent(traceparent: str | None) -> str | None:
    if not traceparent or not isinstance(traceparent, str):
        return None
    parts = traceparent.strip().split("-")
    if len(parts) < 4:
        return None
    trace_id = parts[1]
    if len(trace_id) != 32:
        return None
    return normalize_request_id(trace_id)


def resolve_request_id() -> str:
    direct_request_id = normalize_request_id(request.headers.get("X-Request-ID"))
    if direct_request_id:
        return direct_request_id

    correlation_id = normalize_request_id(request.headers.get("X-Correlation-ID"))
    if correlation_id:
        return correlation_id

    trace_id = request_id_from_traceparent(request.headers.get("traceparent"))
    if trace_id:
        return trace_id

    return uuid.uuid4().hex


def should_log_developer_action(path: str, method: str) -> bool:
    if method not in {"POST", "PUT", "DELETE", "PATCH"}:
        return False
    if path.startswith(("/static/", "/favicon.ico", "/_")):
        return False
    if path in ("/developer/dashboard", "/developer/organizations"):
        return False
    return True


def get_route_required_permissions(endpoint: str | None) -> set[str]:
    if not endpoint:
        return set()
    view_func = current_app.view_functions.get(endpoint)
    if not view_func:
        return set()
    required = getattr(view_func, "_required_permissions", None)
    if not required:
        return set()
    try:
        return set(required)
    except TypeError:
        return {str(required)}


def resolve_route_permission_scope(endpoint: str | None) -> PermissionScope | None:
    required_permissions = get_route_required_permissions(endpoint)
    if not required_permissions:
        return None
    scope = PermissionScope()
    try:
        for permission_name in required_permissions:
            perm_scope = resolve_permission_scope(permission_name)
            scope.dev = scope.dev or perm_scope.dev
            scope.customer = scope.customer or perm_scope.customer
        return scope
    except Exception as exc:
        logger.warning("Failed to resolve route permission scope: %s", exc)
        return None


def classify_route_category(path: str, permission_scope: PermissionScope | None) -> str:
    if permission_scope:
        if permission_scope.is_dev_only:
            return "dev"
        if permission_scope.is_customer_only:
            return "customer"
        return "dev" if RouteAccessConfig.is_developer_only_path(path) else "customer"
    if RouteAccessConfig.is_developer_only_path(path):
        return "dev"
    return "unknown"


def merge_security_headers(configured_headers) -> dict[str, str]:
    security_headers = dict(DEFAULT_SECURITY_HEADERS)
    if isinstance(configured_headers, Mapping):
        security_headers.update(configured_headers)
    elif configured_headers:
        logger.warning("SECURITY_HEADERS must be a mapping; ignoring invalid value.")
    return security_headers
