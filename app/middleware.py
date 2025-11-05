
import os
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass

from flask import request, redirect, url_for, jsonify, session, g, flash
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import joinedload, load_only

from .route_access import RouteAccessConfig
from .utils.cache_manager import app_cache

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


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_UNAUTH_LOG_WINDOW_SECONDS = max(1, _parse_int(os.environ.get('UNAUTH_LOG_WINDOW_SECONDS'), 60))
_UNAUTH_LOG_MAX_PER_WINDOW = _parse_int(os.environ.get('UNAUTH_LOG_MAX_PER_WINDOW'), 50)
_UNAUTH_LOG_STATE = {'window': -1, 'count': 0, 'suppressed': 0}


def _log_rate_limited_unauth(endpoint_info: str, user_agent: str | None) -> None:
    if _UNAUTH_LOG_MAX_PER_WINDOW <= 0:
        return

    if not logger.isEnabledFor(logging.DEBUG):
        return

    current_window = int(time.time() // _UNAUTH_LOG_WINDOW_SECONDS)
    state = _UNAUTH_LOG_STATE

    if state['window'] != current_window:
        if state['suppressed']:
            logger.debug(
                "Suppressed %s unauthenticated requests in previous %ss window (sampled)",
                state['suppressed'],
                _UNAUTH_LOG_WINDOW_SECONDS,
            )
        state['window'] = current_window
        state['count'] = 0
        state['suppressed'] = 0

    if state['count'] < _UNAUTH_LOG_MAX_PER_WINDOW:
        state['count'] += 1
        logger.debug(
            "Unauthenticated access attempt: %s, ua=%s",
            endpoint_info,
            (user_agent or 'Unknown')[:120],
        )
    else:
        state['suppressed'] += 1


_BILLING_CACHE_ENABLED = _env_flag('BILLING_GATE_CACHE_ENABLED', True)
_BILLING_CACHE_TTL_SECONDS = max(5, _parse_int(os.environ.get('BILLING_GATE_CACHE_TTL_SECONDS'), 60))


@dataclass(frozen=True)
class _TierSnapshot:
    id: int | None
    is_billing_exempt: bool
    billing_provider: str | None
    name: str | None = None


class _BillingSnapshot:
    __slots__ = ('id', 'billing_status', 'is_active', '_tier')

    def __init__(self, payload: Mapping[str, object]) -> None:
        self.id = payload.get('id')
        self.billing_status = (payload.get('billing_status') or 'active')  # type: ignore[assignment]
        self.is_active = bool(payload.get('is_active', True))
        tier_payload = payload.get('tier')
        if isinstance(tier_payload, Mapping) and tier_payload.get('id') is not None:
            self._tier = _TierSnapshot(
                id=tier_payload.get('id'),
                is_billing_exempt=bool(tier_payload.get('is_billing_exempt', True)),
                billing_provider=tier_payload.get('billing_provider'),
                name=tier_payload.get('name'),
            )
        else:
            self._tier = None

    @property
    def subscription_tier(self) -> _TierSnapshot | None:
        return self._tier

    @property
    def subscription_tier_obj(self) -> _TierSnapshot | None:
        return self._tier


def _serialize_organization_for_cache(organization) -> dict[str, object]:
    tier = getattr(organization, 'subscription_tier', None)
    return {
        'id': getattr(organization, 'id', None),
        'billing_status': getattr(organization, 'billing_status', 'active') or 'active',
        'is_active': bool(getattr(organization, 'is_active', True)),
        'tier': None if tier is None else {
            'id': getattr(tier, 'id', None),
            'is_billing_exempt': bool(getattr(tier, 'is_billing_exempt', True)),
            'billing_provider': getattr(tier, 'billing_provider', None),
            'name': getattr(tier, 'name', None),
        },
    }

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
                logger.warning(f"Unauthenticated request to UNKNOWN endpoint: {endpoint_info}, user_agent={request.headers.get('User-Agent', 'Unknown')[:100]}")
            elif not request.path.startswith('/static/'):
                _log_rate_limited_unauth(endpoint_info, request.headers.get('User-Agent'))

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
                logger.debug(
                    "Developer checkpoint for %s on %s",
                    getattr(current_user, 'id', 'unknown'),
                    request.path,
                )
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

            # IMPORTANT: Developers bypass the billing check below.
            logger.info(
                "Developer %s bypassed billing on %s %s (masquerade_org=%s)",
                getattr(current_user, 'id', 'unknown'),
                request.method,
                request.path,
                session.get("masquerade_org_id") or session.get("dev_selected_org_id"),
            )
            return

        # 8. Enforce billing for all regular, authenticated users.
        if current_user.is_authenticated and getattr(current_user, 'user_type', None) != 'developer':
            # CRITICAL FIX: Guard DB calls; degrade gracefully if DB is down
            try:
                from .models import Organization
                from .models.subscription_tier import SubscriptionTier
                from .extensions import db
                from .services.billing_service import BillingService  # Import BillingService

                org_for_billing = None
                org_db_instance = None
                org_id = getattr(current_user, 'organization_id', None)
                cache_key = f"billing:snapshot:{org_id}" if org_id else None

                if org_id:
                    cached_payload = app_cache.get(cache_key) if (_BILLING_CACHE_ENABLED and cache_key) else None
                    if cached_payload:
                        org_for_billing = _BillingSnapshot(cached_payload)
                        g.billing_gate_organization = org_for_billing
                        g.billing_gate_cache_state = 'hit'
                    else:
                        stmt = (
                            select(Organization)
                            .options(
                                load_only(
                                    Organization.id,
                                    Organization.billing_status,
                                    Organization.is_active,
                                    Organization.subscription_tier_id,
                                ),
                                joinedload(Organization.subscription_tier).load_only(
                                    SubscriptionTier.id,
                                    SubscriptionTier.billing_provider,
                                    SubscriptionTier.name,
                                ),
                            )
                            .where(Organization.id == org_id)
                        )
                        org_db_instance = db.session.execute(stmt).scalars().first()
                        if org_db_instance:
                            serialized = _serialize_organization_for_cache(org_db_instance)
                            org_for_billing = _BillingSnapshot(serialized)
                            g.billing_gate_organization = org_for_billing
                            g.billing_gate_cache_state = 'miss' if _BILLING_CACHE_ENABLED else 'disabled'
                            if _BILLING_CACHE_ENABLED and cache_key:
                                app_cache.set(cache_key, serialized, ttl=_BILLING_CACHE_TTL_SECONDS)
                    elif not _BILLING_CACHE_ENABLED:
                        g.billing_gate_cache_state = 'disabled'
                else:
                    g.billing_gate_cache_state = 'skip'

                if org_for_billing is None and org_db_instance is not None:
                    # Fallback when snapshot creation failed for any reason
                    org_for_billing = org_db_instance
                    g.billing_gate_organization = org_db_instance

                if org_for_billing and getattr(org_for_billing, 'subscription_tier', None):
                    tier = getattr(org_for_billing, 'subscription_tier')

                    # SIMPLE BILLING LOGIC:
                    # If billing bypass is NOT enabled, require active billing status
                    if not getattr(tier, 'is_billing_exempt', True):  # Default to exempt to prevent lockouts
                        # Direct status enforcement as a guardrail
                        billing_status = getattr(org_for_billing, 'billing_status', 'active') or 'active'
                        if billing_status in ['payment_failed', 'past_due', 'suspended', 'canceled', 'cancelled']:
                            if billing_status in ['payment_failed', 'past_due']:
                                return redirect(url_for('billing.upgrade'))
                            if billing_status in ['suspended', 'canceled', 'cancelled']:
                                try:
                                    flash('Your organization does not have an active subscription. Please update billing.', 'error')
                                except Exception:
                                    pass
                                return redirect(url_for('billing.upgrade'))

                        # Check tier access using unified billing service
                        access_valid, access_reason = BillingService.validate_tier_access(org_for_billing)
                        if not access_valid:
                            logger.warning(f"Billing access denied for org {getattr(org_for_billing, 'id', 'unknown')}: {access_reason}")

                            if access_reason in ['payment_required', 'subscription_canceled']:
                                return redirect(url_for('billing.upgrade'))
                            if access_reason == 'organization_suspended':
                                try:
                                    flash('Your organization has been suspended. Please contact support.', 'error')
                                except Exception:
                                    pass
                                return redirect(url_for('billing.upgrade'))
            except Exception as e:
                # On DB error, rollback and degrade: allow request to proceed without billing gate
                logger.warning(f"Billing check failed, allowing request to proceed: {e}")
                try:
                    from .extensions import db
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
