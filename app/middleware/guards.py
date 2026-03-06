"""Middleware guard handlers.

Synopsis:
Contains focused guard functions for edge-origin auth, developer context, and
billing enforcement.

Glossary:
- Edge-origin auth: Shared-secret header check for trusted edge traffic.
- Developer context: Session-backed org selection/masquerade state for dev users.
- Billing enforcement: Access gating based on orchestrated billing decision actions.
"""

from __future__ import annotations

import hmac
import logging

from flask import flash, g, jsonify, redirect, request, session, url_for
from flask_login import current_user, logout_user

from ..extensions import db
from ..route_access import RouteAccessConfig
from ..services.billing_access_policy_service import BillingAccessAction
from ..services.billing.orchestrators.auth_billing_orchestrator import (
    AuthBillingOrchestrator,
)
from ..services.public_bot_trap_service import PublicBotTrapService
from ..services.session_service import SessionService
from .common import (
    classify_route_category,
    config_csv,
    config_flag,
    config_str,
    path_matches_rule,
    resolve_route_permission_scope,
    should_log_developer_action,
    wants_json_response,
)

logger = logging.getLogger(__name__)


def enforce_edge_origin_auth(app):
    if not config_flag("ENFORCE_EDGE_ORIGIN_AUTH", app=app):
        return None

    request_path = request.path or "/"
    exempt_rules = config_csv("EDGE_ORIGIN_AUTH_EXEMPT_PATHS", "/health", app=app)
    if any(path_matches_rule(request_path, rule) for rule in exempt_rules):
        return None

    expected_secret = config_str("EDGE_ORIGIN_AUTH_SECRET", "", app=app)
    if not expected_secret:
        logger.error(
            "ENFORCE_EDGE_ORIGIN_AUTH is enabled but EDGE_ORIGIN_AUTH_SECRET is empty."
        )
        return ("Service unavailable", 503)

    header_name = config_str("EDGE_ORIGIN_AUTH_HEADER", "X-Edge-Origin-Auth", app=app)
    provided_secret = request.headers.get(header_name, "")
    if hmac.compare_digest(str(provided_secret), expected_secret):
        return None

    logger.warning(
        "Blocked request missing valid edge origin auth header: path=%s ip=%s ua=%s",
        request_path,
        PublicBotTrapService.resolve_request_ip(request),
        (request.headers.get("User-Agent") or "-")[:160],
    )
    if wants_json_response():
        return jsonify({"error": "Forbidden"}), 403
    return ("Forbidden", 403)


def force_logout_for_billing_lock() -> None:
    try:
        if current_user.is_authenticated:
            current_user.active_session_token = None
            db.session.commit()
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/middleware/guards.py:64",
            exc_info=True,
        )
        try:
            db.session.rollback()
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/middleware/guards.py:70",
                exc_info=True,
            )
    finally:
        try:
            SessionService.clear_session_state()
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/middleware/guards.py:78",
                exc_info=True,
            )
        try:
            logout_user()
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/middleware/guards.py:84",
                exc_info=True,
            )


def handle_developer_context(path: str, endpoint: str | None, permission_scope=None):
    try:
        selected_org_id = session.get("dev_selected_org_id")
        masquerade_org_id = session.get("masquerade_org_id")
        allowed_without_org = RouteAccessConfig.is_developer_no_org_required(path)

        if permission_scope is None:
            permission_scope = resolve_route_permission_scope(endpoint)

        route_category = classify_route_category(path, permission_scope)
        requires_org = route_category in {"customer", "unknown"} and not allowed_without_org

        if requires_org and not (selected_org_id or masquerade_org_id):
            try:
                flash(
                    "Please select an organization to view customer features.",
                    "warning",
                )
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/middleware/guards.py:108",
                    exc_info=True,
                )
            return redirect(url_for("developer.organizations"))

        effective_org_id = selected_org_id or masquerade_org_id
        if effective_org_id:
            try:
                from ..models import Organization

                g.effective_org = db.session.get(Organization, effective_org_id)
                g.is_developer_masquerade = True
            except Exception as exc:
                logger.warning("Could not set masquerade context: %s", exc)
                g.effective_org = None
                g.is_developer_masquerade = False

        if should_log_developer_action(path, request.method):
            user_id = getattr(current_user, "id", "unknown")
            logger.info("Developer %s performing %s %s", user_id, request.method, path)
        return None
    except Exception as exc:
        logger.warning("Developer masquerade logic failed: %s", exc)
        return None


def enforce_billing():
    try:
        from ..models import Organization

        organization = getattr(current_user, "organization", None)
        if organization is None:
            org_id = getattr(current_user, "organization_id", None)
            if org_id:
                organization = db.session.get(Organization, org_id)

        if not organization:
            return None

        path = request.path
        endpoint = request.endpoint
        is_exempt_request = AuthBillingOrchestrator.is_enforcement_exempt_route(
            path, endpoint
        )
        decision = AuthBillingOrchestrator.evaluate_organization_access(organization)

        if decision.action == BillingAccessAction.ALLOW:
            return None

        logger.warning(
            "Billing access decision for org %s: action=%s reason=%s",
            getattr(organization, "id", None),
            decision.action,
            decision.reason,
        )

        if decision.action == BillingAccessAction.HARD_LOCK:
            force_logout_for_billing_lock()
            if wants_json_response():
                return (
                    jsonify(
                        {
                            "error": "organization_inactive",
                            "message": decision.message,
                        }
                    ),
                    403,
                )
            try:
                flash(decision.message, "error")
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/middleware/guards.py:188",
                    exc_info=True,
                )
            return redirect(url_for("auth.login"))

        if decision.action == BillingAccessAction.REQUIRE_UPGRADE:
            if is_exempt_request:
                return None
            if wants_json_response():
                return (
                    jsonify(
                        {
                            "error": "billing_required",
                            "message": decision.message,
                            "upgrade_url": url_for("billing.upgrade"),
                        }
                    ),
                    403,
                )
            try:
                flash(decision.message, "warning")
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/middleware/guards.py:210",
                    exc_info=True,
                )
            return redirect(url_for("billing.upgrade"))

        return None
    except Exception as exc:
        logger.warning("Billing check failed, allowing request to proceed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/middleware/guards.py:222",
                exc_info=True,
            )
        return None


def enforce_customer_onboarding_completion():
    """Keep first-run onboarding mandatory until checklist completion."""
    if not current_user.is_authenticated:
        return None
    if getattr(current_user, "user_type", None) != "customer":
        return None

    first_name = (getattr(current_user, "first_name", None) or "").strip()
    last_name = (getattr(current_user, "last_name", None) or "").strip()
    missing_required_profile = not (first_name and last_name)
    requires_onboarding = bool(session.get("onboarding_welcome")) or missing_required_profile
    if not requires_onboarding:
        return None

    endpoint = request.endpoint or ""
    path = request.path or ""
    if endpoint == "onboarding.welcome" or path.startswith("/onboarding/"):
        return None

    if wants_json_response():
        return (
            jsonify(
                {
                    "error": "onboarding_required",
                    "message": "Complete onboarding before continuing.",
                    "redirect_url": url_for("onboarding.welcome"),
                }
            ),
            428,
        )

    if not session.get("onboarding_completion_required_notice"):
        flash("Please complete onboarding before continuing.", "warning")
        session["onboarding_completion_required_notice"] = True
    return redirect(url_for("onboarding.welcome"))
