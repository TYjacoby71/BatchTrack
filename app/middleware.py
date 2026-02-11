"""Request middleware for security and permissions.

Synopsis:
Applies security headers, access checks, and bot trap defenses.

Glossary:
- Security headers: HTTP headers that harden browser behavior.
- Route access: Permission and role gating for endpoints.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from flask import (
    Flask,
    Response,
    current_app,
    flash,
    g,
    has_app_context,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)
from flask_login import current_user, logout_user

from .extensions import db
from .route_access import RouteAccessConfig
from .utils.permissions import PermissionScope, resolve_permission_scope
from .services.middleware_probe_service import MiddlewareProbeService
from .services.public_bot_trap_service import PublicBotTrapService

logger = logging.getLogger(__name__)

DEFAULT_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https://api.stripe.com; "
        "frame-src https://js.stripe.com; "
        "object-src 'none'"
    ),
}


# --- Config flag ---
# Purpose: Resolve boolean config values from app config.
def _config_flag(name: str, default: bool = False, *, app: Flask | None = None) -> bool:
    if app is None and has_app_context():
        app = current_app._get_current_object()
    value = app.config.get(name, default) if app is not None else default
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# --- Config int ---
# Purpose: Resolve integer config values from app config.
def _config_int(name: str, default: int, *, app: Flask | None = None) -> int:
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


# --- Wants JSON response ---
# Purpose: Detect when a request should return JSON instead of HTML.
def _wants_json_response() -> bool:
    accepts = request.accept_mimetypes
    return request.path.startswith("/api/") or (
        "application/json" in accepts and not accepts.accept_html
    )


# --- Developer action logging ---
# Purpose: Decide whether a developer action should be logged.
def _should_log_developer_action(path: str, method: str) -> bool:
    if method not in {"POST", "PUT", "DELETE", "PATCH"}:
        return False
    if path.startswith(("/static/", "/favicon.ico", "/_")):
        return False
    if path in ("/developer/dashboard", "/developer/organizations"):
        return False
    return True


# --- Route permissions ---
# Purpose: Look up required permissions for the given endpoint.
def _get_route_required_permissions(endpoint: str | None) -> set[str]:
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


# --- Route permission scope ---
# Purpose: Map endpoints to permission scopes for auditing.
def _resolve_route_permission_scope(endpoint: str | None) -> PermissionScope | None:
    required_permissions = _get_route_required_permissions(endpoint)
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


# --- Route category ---
# Purpose: Classify routes for analytics and logging.
def _classify_route_category(path: str, permission_scope: PermissionScope | None) -> str:
    if permission_scope:
        if permission_scope.is_dev_only:
            return "dev"
        if permission_scope.is_customer_only:
            return "customer"
        return "dev" if RouteAccessConfig.is_developer_only_path(path) else "customer"
    if RouteAccessConfig.is_developer_only_path(path):
        return "dev"
    return "unknown"


# --- Register middleware ---
# Purpose: Attach security and access middleware to the Flask app.
def register_middleware(app: Flask) -> None:
    """Attach global middleware to the Flask app."""

    trust_proxy_headers = _config_flag("ENABLE_PROXY_FIX", app=app) or _config_flag("TRUST_PROXY_HEADERS", app=app)
    if trust_proxy_headers and not getattr(app.wsgi_app, "_batchtrack_proxyfix", False):
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
        except Exception as exc:  # pragma: no cover
            logger.warning("ProxyFix unavailable; unable to honor proxy header trust: %s", exc)
        else:
            proxy_fix_kwargs = {
                "x_for": _config_int("PROXY_FIX_X_FOR", 1, app=app),
                "x_proto": _config_int("PROXY_FIX_X_PROTO", 1, app=app),
                "x_host": _config_int("PROXY_FIX_X_HOST", 1, app=app),
                "x_port": _config_int("PROXY_FIX_X_PORT", 1, app=app),
                "x_prefix": _config_int("PROXY_FIX_X_PREFIX", 0, app=app),
            }
            wrapped = ProxyFix(app.wsgi_app, **proxy_fix_kwargs)
            setattr(wrapped, "_batchtrack_proxyfix", True)
            app.wsgi_app = wrapped

    secure_env = not app.debug and not app.testing
    force_security_headers = _config_flag("FORCE_SECURITY_HEADERS", app=app)
    disable_security_headers = _config_flag("DISABLE_SECURITY_HEADERS", app=app)

    configured_headers = app.config.get("SECURITY_HEADERS")
    security_headers = dict(DEFAULT_SECURITY_HEADERS)
    if isinstance(configured_headers, Mapping):
        security_headers.update(configured_headers)
    elif configured_headers:
        logger.warning("SECURITY_HEADERS must be a mapping; ignoring invalid value.")

    custom_csp = app.config.get("CONTENT_SECURITY_POLICY")
    if custom_csp is None:
        security_headers.pop("Content-Security-Policy", None)
    elif isinstance(custom_csp, str) and custom_csp.strip():
        security_headers["Content-Security-Policy"] = custom_csp.strip()
    elif custom_csp:
        logger.warning("CONTENT_SECURITY_POLICY must be a non-empty string or None.")

    @app.before_request
    def single_security_checkpoint() -> Response | None:
        path = request.path

        if RouteAccessConfig.is_monitoring_request(request):
            return None

        if path.startswith("/static/"):
            return None

        if current_app.config.get("SKIP_PERMISSIONS") or current_app.config.get("TESTING_DISABLE_AUTH"):
            return None

        try:
            if PublicBotTrapService.should_block_request(request, current_user):
                logger.warning(
                    "Blocked request from bot trap: path=%s ip=%s user_id=%s",
                    path,
                    PublicBotTrapService.resolve_request_ip(request),
                    getattr(current_user, "id", None),
                )
                if current_user.is_authenticated:
                    try:
                        logout_user()
                    except Exception:
                        pass
                if _wants_json_response():
                    return jsonify({"error": "Access blocked"}), 403
                return ("Forbidden", 403)
        except Exception as exc:
            logger.warning("Bot trap block check failed: %s", exc)

        if RouteAccessConfig.is_public_endpoint(request.endpoint):
            return None

        if RouteAccessConfig.is_public_path(path):
            return None

        if not current_user.is_authenticated:
            endpoint_info = f"endpoint={request.endpoint}, path={path}, method={request.method}"
            level_name = str(current_app.config.get("ANON_REQUEST_LOG_LEVEL", "DEBUG")).upper()
            log_level = getattr(logging, level_name, logging.DEBUG)
            if request.endpoint is None:
                status_code = MiddlewareProbeService.derive_unknown_endpoint_status(request)
                if status_code is None:
                    return None
                MiddlewareProbeService.maybe_block_suspicious_unknown_probe(
                    request=request,
                    path=path,
                    status_code=status_code,
                )
                logger.warning(
                    "Unauthenticated request to unknown endpoint: %s; user_agent=%s",
                    endpoint_info,
                    request.headers.get("User-Agent", "unknown")[:100],
                )
                if _wants_json_response():
                    message = "Method not allowed" if status_code == 405 else "Not found"
                    return jsonify({"error": message}), status_code
                body = "Method Not Allowed" if status_code == 405 else "Not Found"
                return (body, status_code)
            elif logger.isEnabledFor(log_level):
                logger.log(log_level, "Unauthenticated access attempt: %s", endpoint_info)

            if _wants_json_response():
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login", next=request.url))

        permission_scope = _resolve_route_permission_scope(request.endpoint)

        try:
            if RouteAccessConfig.is_developer_only_path(path):
                if getattr(current_user, "user_type", None) != "developer":
                    if _wants_json_response():
                        return jsonify({"error": "forbidden", "reason": "developer_only"}), 403
                    try:
                        flash("Developer access required.", "error")
                    except Exception:
                        pass
                    return redirect(url_for("app_routes.dashboard"))
        except Exception as exc:  # pragma: no cover - avoid hard failures
            logger.warning("Developer access check failed: %s", exc)

        if permission_scope and permission_scope.is_dev_only:
            if getattr(current_user, "user_type", None) != "developer":
                if _wants_json_response():
                    return jsonify({"error": "forbidden", "reason": "developer_only"}), 403
                try:
                    flash("Developer access required.", "error")
                except Exception:
                    pass
                return redirect(url_for("app_routes.dashboard"))

        if getattr(current_user, "user_type", None) == "developer":
            return _handle_developer_context(path, request.endpoint, permission_scope)

        if getattr(current_user, "user_type", None) != "developer":
            billing_redirect = _enforce_billing()
            if billing_redirect is not None:
                return billing_redirect

        return None

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        if disable_security_headers:
            return response

        if not (secure_env or force_security_headers):
            return response

        def _is_effectively_secure() -> bool:
            if request.is_secure:
                return True
            forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
            if forwarded_proto:
                forwarded_values = {value.strip().lower() for value in forwarded_proto.split(",")}
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


# --- Handle developer context ---
# Purpose: Emit dev-context payloads for audit and UI diagnostics.
def _handle_developer_context(
    path: str,
    endpoint: str | None,
    permission_scope: PermissionScope | None = None,
) -> Response | None:
    try:
        selected_org_id = session.get("dev_selected_org_id")
        masquerade_org_id = session.get("masquerade_org_id")
        allowed_without_org = RouteAccessConfig.is_developer_no_org_required(path)

        if permission_scope is None:
            permission_scope = _resolve_route_permission_scope(endpoint)

        route_category = _classify_route_category(path, permission_scope)
        requires_org = route_category in {"customer", "unknown"} and not allowed_without_org

        if requires_org and not (selected_org_id or masquerade_org_id):
            try:
                flash("Please select an organization to view customer features.", "warning")
            except Exception:
                pass
            return redirect(url_for("developer.organizations"))

        effective_org_id = selected_org_id or masquerade_org_id
        if effective_org_id:
            try:
                from .models import Organization

                g.effective_org = db.session.get(Organization, effective_org_id)
                g.is_developer_masquerade = True
            except Exception as exc:
                logger.warning("Could not set masquerade context: %s", exc)
                g.effective_org = None
                g.is_developer_masquerade = False

        if _should_log_developer_action(path, request.method):
            user_id = getattr(current_user, "id", "unknown")
            logger.info("Developer %s performing %s %s", user_id, request.method, path)
        return None
    except Exception as exc:
        logger.warning("Developer masquerade logic failed: %s", exc)
        return None


# --- Enforce billing ---
# Purpose: Gate routes based on billing status and entitlements.
def _enforce_billing() -> Response | None:
    try:
        from .models import Organization
        from .services.billing_service import BillingService

        organization = getattr(current_user, "organization", None)
        if organization is None:
            org_id = getattr(current_user, "organization_id", None)
            if org_id:
                organization = db.session.get(Organization, org_id)

        if not organization:
            return None

        tier_obj = getattr(organization, "subscription_tier_obj", None)
        billing_status = (organization.billing_status or "active").lower()

        if tier_obj and not tier_obj.is_billing_exempt:
            if billing_status in {"payment_failed", "past_due"}:
                return redirect(url_for("billing.upgrade"))
            if billing_status in {"suspended", "canceled", "cancelled"}:
                try:
                    flash("Your organization does not have an active subscription. Please update billing.", "error")
                except Exception:
                    pass
                return redirect(url_for("billing.upgrade"))

        access_valid, access_reason = BillingService.validate_tier_access(organization)
        if not access_valid:
            logger.warning(
                "Billing access denied for org %s: %s",
                getattr(organization, "id", None),
                access_reason,
            )
            if access_reason in {"payment_required", "subscription_canceled"}:
                return redirect(url_for("billing.upgrade"))
            if access_reason == "organization_suspended":
                try:
                    flash("Your organization has been suspended. Please contact support.", "error")
                except Exception:
                    pass
                return redirect(url_for("billing.upgrade"))

        return None
    except Exception as exc:
        logger.warning("Billing check failed, allowing request to proceed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
        return None