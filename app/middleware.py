import os
import logging
from collections.abc import Mapping

from flask import request, redirect, url_for, jsonify, session, g, flash, current_app
from flask_login import current_user

from .route_access import RouteAccessConfig
from .extensions import db

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


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Configure logger
logger = logging.getLogger(__name__)

def register_middleware(app):
    """Register all middleware functions with the Flask app."""

    trust_proxy_headers = _env_flag("ENABLE_PROXY_FIX") or _env_flag("TRUST_PROXY_HEADERS")
    if trust_proxy_headers and not getattr(app.wsgi_app, "_batchtrack_proxyfix", False):
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
        except Exception as exc:  # pragma: no cover - safety net for minimal deployments
            logger.warning("ProxyFix unavailable; unable to honor proxy header trust: %s", exc)
        else:
            def _safe_env_int(name: str, default: int) -> int:
                raw = os.environ.get(name)
                if raw is None:
                    return default
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    logger.warning("Invalid value for %s=%r; defaulting to %s", name, raw, default)
                    return default

            proxy_fix_kwargs = {
                "x_for": _safe_env_int("PROXY_FIX_X_FOR", 1),
                "x_proto": _safe_env_int("PROXY_FIX_X_PROTO", 1),
                "x_host": _safe_env_int("PROXY_FIX_X_HOST", 1),
                "x_port": _safe_env_int("PROXY_FIX_X_PORT", 1),
                "x_prefix": _safe_env_int("PROXY_FIX_X_PREFIX", 0),
            }

            wrapped = ProxyFix(app.wsgi_app, **proxy_fix_kwargs)
            setattr(wrapped, "_batchtrack_proxyfix", True)
            app.wsgi_app = wrapped

    secure_env = not app.debug and not app.testing
    force_security_headers = _env_flag("FORCE_SECURITY_HEADERS")
    disable_security_headers = _env_flag("DISABLE_SECURITY_HEADERS")

    configured_headers = app.config.get("SECURITY_HEADERS")
    security_headers = dict(DEFAULT_SECURITY_HEADERS)
    if isinstance(configured_headers, Mapping):
        security_headers.update(configured_headers)
    elif configured_headers:
        logger.warning("SECURITY_HEADERS config must be a mapping; ignoring invalid value.")

    custom_csp = app.config.get("CONTENT_SECURITY_POLICY")
    if custom_csp is None:
        security_headers.pop("Content-Security-Policy", None)
    elif isinstance(custom_csp, str) and custom_csp.strip():
        security_headers["Content-Security-Policy"] = custom_csp.strip()
    elif custom_csp:
        logger.warning("CONTENT_SECURITY_POLICY config must be a non-empty string or None.")

    @app.before_request
    def single_security_checkpoint():
        """
        The single, unified security checkpoint for every request.
        Checks are performed in order from least to most expensive.

        Access rules are defined in route_access.py for maintainability.
        """
        # 1. Fast-path for monitoring/health checks - skip ALL middleware
        if RouteAccessConfig.is_monitoring_request(request):
            return

        # 2. Fast-path for static files
        if request.path.startswith('/static/'):
            return

        # 3. Fast-path for public endpoints (by endpoint name)
        if RouteAccessConfig.is_public_endpoint(request.endpoint):
            return

        # 4. Fast-path for public paths (by path prefix)
        if RouteAccessConfig.is_public_path(request.path):
            return

        # 5. Authentication check - if we get here, user must be authenticated
        if not current_user.is_authenticated:
            # Better debugging: log the actual path and method being requested
            endpoint_info = f"endpoint={request.endpoint}, path={request.path}, method={request.method}"
            if request.endpoint is None:
                logger.warning(
                    "Unauthenticated request to UNKNOWN endpoint: %s, user_agent=%s",
                    endpoint_info,
                    request.headers.get('User-Agent', 'Unknown')[:100],
                )
            elif not request.path.startswith('/static/'):
                level_name = str(current_app.config.get('ANON_REQUEST_LOG_LEVEL', 'DEBUG')).upper()
                log_level = getattr(logging, level_name, logging.DEBUG)
                if logger.isEnabledFor(log_level):
                    logger.log(log_level, f"Unauthenticated access attempt: {endpoint_info}")

            # Return JSON 401 for API or JSON-accepting requests
            accept = request.accept_mimetypes
            wants_json = request.path.startswith('/api/') or ("application/json" in accept and not accept.accept_html)
            if wants_json:
                return jsonify({"error": "Authentication required"}), 401

            return redirect(url_for('auth.login', next=request.url))

        # 6. Block non-developers from accessing developer-only routes
        try:
            if RouteAccessConfig.is_developer_only_path(request.path):
                user_type = getattr(current_user, 'user_type', None)
                if user_type != 'developer':
                    accept = request.accept_mimetypes
                    wants_json = request.path.startswith('/api/') or ("application/json" in accept and not accept.accept_html)
                    if wants_json:
                        return jsonify({"error": "forbidden", "reason": "developer_only"}), 403
                    try:
                        flash('Developer access required.', 'error')
                    except Exception:
                        pass
                    return redirect(url_for('app_routes.dashboard'))
        except Exception as e:
            # Log the error but don't fail closed - allow request to proceed
            logger.warning(f"Developer access check failed: {e}")

        # 7. Handle developer "super admin" and masquerade logic.
        if getattr(current_user, 'user_type', None) == 'developer':            
            try:
                selected_org_id = session.get("dev_selected_org_id")
                masquerade_org_id = session.get("masquerade_org_id")  # Support both session keys

                # If no org selected, redirect to organization selection unless allowed
                allowed_without_org = RouteAccessConfig.is_developer_no_org_required(request.path)
                if not selected_org_id and not masquerade_org_id and not allowed_without_org:
                    try:
                        flash("Please select an organization to view customer features.", "warning")
                    except Exception:
                        pass
                    return redirect(url_for("developer.organizations"))

                # If an org is selected, set it as the effective org for the request
                effective_org_id = selected_org_id or masquerade_org_id
                if effective_org_id:
                    try:
                        from .models import Organization
                        from .extensions import db
                        g.effective_org = db.session.get(Organization, effective_org_id)
                        g.is_developer_masquerade = True
                    except Exception as e:
                        # If DB is unavailable, continue without masquerade context
                        logger.warning(f"Could not set masquerade context: {e}")
                        g.effective_org = None
                        g.is_developer_masquerade = False
            except Exception as e:
                logger.warning(f"Developer masquerade logic failed: {e}")

            # Log only for non-static requests and meaningful operations
            should_log = (
                not request.path.startswith('/static/') and
                not request.path.startswith('/favicon.ico') and
                not request.path.startswith('/_') and  # Skip internal routes
                request.method in ['POST', 'PUT', 'DELETE', 'PATCH']
            )

            # Skip logging for frequent developer dashboard calls and GET requests
            if (request.path in ['/developer/dashboard', '/developer/organizations'] or 
                request.method == 'GET'):
                should_log = False

            if should_log and current_user and current_user.is_authenticated:
                # Only log actual modifications, not routine access
                user_id = getattr(current_user, 'id', 'unknown')
                logger.info(f"Developer {user_id} performing {request.method} {request.path}")
            return

        # 8. Enforce billing for all regular, authenticated users.
        if current_user.is_authenticated and getattr(current_user, 'user_type', None) != 'developer':
            try:
                from .services.billing_service import BillingService
                from .models import Organization

                organization = getattr(current_user, 'organization', None)
                if not organization:
                    org_id = getattr(current_user, 'organization_id', None)
                    if org_id:
                        organization = db.session.get(Organization, org_id)

                if organization:
                    tier_obj = getattr(organization, 'subscription_tier_obj', None)
                    billing_status = (organization.billing_status or 'active').lower()

                    if tier_obj and not tier_obj.is_billing_exempt:
                        if billing_status in ['payment_failed', 'past_due']:
                            return redirect(url_for('billing.upgrade'))
                        if billing_status in ['suspended', 'canceled', 'cancelled']:
                            try:
                                flash('Your organization does not have an active subscription. Please update billing.', 'error')
                            except Exception:
                                pass
                            return redirect(url_for('billing.upgrade'))

                    access_valid, access_reason = BillingService.validate_tier_access(organization)
                    if not access_valid:
                        logger.warning(f"Billing access denied for org {getattr(organization, 'id', None)}: {access_reason}")

                        if access_reason in ['payment_required', 'subscription_canceled']:
                            return redirect(url_for('billing.upgrade'))
                        if access_reason == 'organization_suspended':
                            try:
                                flash('Your organization has been suspended. Please contact support.', 'error')
                            except Exception:
                                pass
                            return redirect(url_for('billing.upgrade'))
            except Exception as e:
                logger.warning(f"Billing check failed, allowing request to proceed: {e}")
                try:
                    db.session.rollback()
                except Exception:
                    pass

        # 9. If all checks pass, allow the request to proceed.
        return None

    @app.after_request
    def add_security_headers(response):
        """Add security headers when running in production-like environments."""

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
            if header_value in (None, ""):
                continue

            if header_name.lower() == "strict-transport-security" and not enforce_hsts:
                continue

            response.headers.setdefault(header_name, header_value)

        return response