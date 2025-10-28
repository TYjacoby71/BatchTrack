import os
from flask import request, redirect, url_for, jsonify, session, g, flash
from flask_login import current_user, logout_user
import logging

from .route_access import RouteAccessConfig

# Configure logger
logger = logging.getLogger(__name__)

def register_middleware(app):
    """Register all middleware functions with the Flask app."""

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
                logger.info(f"Unauthenticated access attempt: {endpoint_info}")

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
        except Exception:
            # If anything goes wrong, fail closed
            return jsonify({"error": "forbidden"}), 403

        # Force reload current_user to ensure fresh session data
        from flask_login import current_user as fresh_current_user

        # 7. Handle developer "super admin" and masquerade logic.
        if getattr(fresh_current_user, 'user_type', None) == 'developer':
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
                except Exception:
                    # If DB is unavailable, continue without masquerade context
                    g.effective_org = None
                    g.is_developer_masquerade = False

            # IMPORTANT: Developers bypass the billing check below.
            return

        # 8. Enforce billing for all regular, authenticated users.
        if fresh_current_user.is_authenticated and getattr(fresh_current_user, 'user_type', None) != 'developer':
            # CRITICAL FIX: Guard DB calls; degrade gracefully if DB is down
            try:
                # Force fresh database query to avoid session isolation issues
                from .models import User, Organization
                from .extensions import db
                from .services.billing_service import BillingService # Import BillingService

                # Get fresh user and organization data from current session
                fresh_user = db.session.get(User, fresh_current_user.id)
                if fresh_user and fresh_user.organization_id:
                    # Force fresh load of organization to get latest billing_status
                    organization = db.session.get(Organization, fresh_user.organization_id)
                else:
                    organization = None

                if organization and organization.subscription_tier:
                    tier = organization.subscription_tier

                    # SIMPLE BILLING LOGIC:
                    # If billing bypass is NOT enabled, require active billing status
                    if not tier.is_billing_exempt:
                        # Direct status enforcement as a guardrail
                        billing_status = getattr(organization, 'billing_status', 'active') or 'active'
                        if billing_status in ['payment_failed', 'past_due', 'suspended', 'canceled', 'cancelled']:
                            if billing_status in ['payment_failed', 'past_due']:
                                return redirect(url_for('billing.upgrade'))
                            elif billing_status in ['suspended', 'canceled', 'cancelled']:
                                try:
                                    flash('Your organization does not have an active subscription. Please update billing.', 'error')
                                except Exception:
                                    pass
                                return redirect(url_for('billing.upgrade'))

                        # Check tier access using unified billing service
                        access_valid, access_reason = BillingService.validate_tier_access(organization)
                        if not access_valid:
                            logger.warning(f"Billing access denied for org {organization.id}: {access_reason}")

                            if access_reason in ['payment_required', 'subscription_canceled']:
                                return redirect(url_for('billing.upgrade'))
                            elif access_reason == 'organization_suspended':
                                try:
                                    flash('Your organization has been suspended. Please contact support.', 'error')
                                except Exception:
                                    pass
                                return redirect(url_for('billing.upgrade'))
            except Exception:
                # On DB error, rollback and degrade: allow request to proceed without billing gate
                try:
                    from .extensions import db
                    db.session.rollback()
                except Exception:
                    pass

        # 9. If all checks pass, allow the request to proceed.
        return None

    @app.after_request
    def add_security_headers(response):
        """Add security headers in production."""
        if os.environ.get("REPLIT_DEPLOYMENT") == "true":
            response.headers.update({
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
            })
        return response