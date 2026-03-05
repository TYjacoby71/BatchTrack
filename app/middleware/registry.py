"""Middleware registration and request pipeline.

Synopsis:
Composes common helpers and focused guards into the request/response middleware
chain while preserving execution order.

Glossary:
- Before-request hook: Function executed before route handlers.
- After-request hook: Function executed after route handlers.
- Passive public asset: Static/SEO path that bypasses heavy middleware checks.
"""

from __future__ import annotations

import logging
import time

from flask import Flask, Response, current_app, g, jsonify, redirect, request, url_for
from flask_login import current_user, logout_user

from ..route_access import RouteAccessConfig
from ..services.middleware_probe_service import MiddlewareProbeService
from ..services.public_bot_trap_service import PublicBotTrapService
from .common import (
    config_flag,
    config_int,
    merge_security_headers,
    resolve_request_id,
    resolve_route_permission_scope,
    wants_json_response,
)
from .guards import enforce_billing, enforce_edge_origin_auth, handle_developer_context
from .security_headers import apply_security_headers

logger = logging.getLogger(__name__)


def register_middleware(app: Flask) -> None:
    """Attach global middleware to the Flask app."""

    trust_proxy_headers = config_flag("ENABLE_PROXY_FIX", app=app) or config_flag(
        "TRUST_PROXY_HEADERS", app=app
    )
    if trust_proxy_headers and not getattr(app.wsgi_app, "_batchtrack_proxyfix", False):
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ProxyFix unavailable; unable to honor proxy header trust: %s", exc
            )
        else:
            proxy_fix_kwargs = {
                "x_for": config_int("PROXY_FIX_X_FOR", 1, app=app),
                "x_proto": config_int("PROXY_FIX_X_PROTO", 1, app=app),
                "x_host": config_int("PROXY_FIX_X_HOST", 1, app=app),
                "x_port": config_int("PROXY_FIX_X_PORT", 1, app=app),
                "x_prefix": config_int("PROXY_FIX_X_PREFIX", 0, app=app),
            }
            wrapped = ProxyFix(app.wsgi_app, **proxy_fix_kwargs)
            setattr(wrapped, "_batchtrack_proxyfix", True)
            app.wsgi_app = wrapped

    secure_env = not app.debug and not app.testing
    force_security_headers = config_flag("FORCE_SECURITY_HEADERS", app=app)
    disable_security_headers = config_flag("DISABLE_SECURITY_HEADERS", app=app)

    security_headers = merge_security_headers(app.config.get("SECURITY_HEADERS"))
    custom_csp = app.config.get("CONTENT_SECURITY_POLICY")
    if custom_csp is None:
        security_headers.pop("Content-Security-Policy", None)
    elif isinstance(custom_csp, str) and custom_csp.strip():
        security_headers["Content-Security-Policy"] = custom_csp.strip()
    elif custom_csp:
        logger.warning("CONTENT_SECURITY_POLICY must be a non-empty string or None.")

    @app.before_request
    def single_security_checkpoint() -> Response | None:
        g.request_started_at = time.perf_counter()
        request_id = resolve_request_id()
        g.request_id = request_id
        request.environ["HTTP_X_REQUEST_ID"] = request_id

        path = request.path

        edge_origin_auth_response = enforce_edge_origin_auth(app)
        if edge_origin_auth_response is not None:
            return edge_origin_auth_response

        if RouteAccessConfig.is_monitoring_request(request):
            return None

        if RouteAccessConfig.is_passive_public_asset_path(path):
            return None

        if current_app.config.get("SKIP_PERMISSIONS") or current_app.config.get(
            "TESTING_DISABLE_AUTH"
        ):
            return None

        if MiddlewareProbeService.is_high_confidence_probe_path(path):
            request_ip = PublicBotTrapService.resolve_request_ip(request)
            try:
                PublicBotTrapService.record_hit(
                    request=request,
                    source="middleware_early_path_block",
                    reason="high_confidence_probe_path",
                    extra={"path": path},
                    block=True,
                )
            except Exception as exc:
                logger.debug("Failed to record early path block hit for %s: %s", path, exc)

            logger.warning(
                "Early-blocked high-confidence probe path: path=%s ip=%s user_id=%s",
                path,
                request_ip,
                getattr(current_user, "id", None),
            )
            if current_user.is_authenticated:
                try:
                    logout_user()
                except Exception:
                    logger.warning(
                        "Suppressed exception fallback at app/middleware/registry.py:109",
                        exc_info=True,
                    )
            if wants_json_response():
                return jsonify({"error": "Access blocked"}), 403
            return ("Forbidden", 403)

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
                        logger.warning(
                            "Suppressed exception fallback at app/middleware/registry.py:130",
                            exc_info=True,
                        )
                if wants_json_response():
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
            level_name = str(
                current_app.config.get("ANON_REQUEST_LOG_LEVEL", "DEBUG")
            ).upper()
            log_level = getattr(logging, level_name, logging.DEBUG)
            if request.endpoint is None:
                status_code = MiddlewareProbeService.derive_unknown_endpoint_status(
                    request
                )
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
                if wants_json_response():
                    message = "Method not allowed" if status_code == 405 else "Not found"
                    return jsonify({"error": message}), status_code
                body = "Method Not Allowed" if status_code == 405 else "Not Found"
                return (body, status_code)
            elif logger.isEnabledFor(log_level):
                logger.log(log_level, "Unauthenticated access attempt: %s", endpoint_info)

            if wants_json_response():
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login", next=request.url))

        permission_scope = resolve_route_permission_scope(request.endpoint)

        try:
            if RouteAccessConfig.is_developer_only_path(path):
                if getattr(current_user, "user_type", None) != "developer":
                    if wants_json_response():
                        return (
                            jsonify({"error": "forbidden", "reason": "developer_only"}),
                            403,
                        )
                    try:
                        from flask import flash

                        flash("Developer access required.", "error")
                    except Exception:
                        logger.warning(
                            "Suppressed exception fallback at app/middleware/registry.py:194",
                            exc_info=True,
                        )
                    return redirect(url_for("app_routes.dashboard"))
        except Exception as exc:  # pragma: no cover - avoid hard failures
            logger.warning("Developer access check failed: %s", exc)

        if permission_scope and permission_scope.is_dev_only:
            if getattr(current_user, "user_type", None) != "developer":
                if wants_json_response():
                    return (
                        jsonify({"error": "forbidden", "reason": "developer_only"}),
                        403,
                    )
                try:
                    from flask import flash

                    flash("Developer access required.", "error")
                except Exception:
                    logger.warning(
                        "Suppressed exception fallback at app/middleware/registry.py:213",
                        exc_info=True,
                    )
                return redirect(url_for("app_routes.dashboard"))

        if getattr(current_user, "user_type", None) == "developer":
            return handle_developer_context(path, request.endpoint, permission_scope)

        billing_redirect = enforce_billing()
        if billing_redirect is not None:
            return billing_redirect

        return None

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        return apply_security_headers(
            response,
            app=app,
            request_id=getattr(g, "request_id", None),
            disable_security_headers=disable_security_headers,
            secure_env=secure_env,
            force_security_headers=force_security_headers,
            security_headers=security_headers,
        )
