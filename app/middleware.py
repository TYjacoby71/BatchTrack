import os
from flask import request, redirect, url_for, jsonify, session, g, flash
from flask_login import current_user
from .utils.http import wants_json

def register_middleware(app):
    """Register all middleware functions with the Flask app."""

    @app.before_request
    def single_security_checkpoint():
        """
        The single, unified security checkpoint for every request.
        Checks are performed in order from least to most expensive.
        """
        # 1. Fast-path for completely public endpoints.
        # This is the ONLY list of public routes needed.
        public_endpoints = [
            'static', 'auth.login', 'auth.signup', 'auth.logout',
            'homepage', 'legal.privacy_policy', 'legal.terms_of_service',
            'billing.webhook'  # Stripe webhook is a critical public endpoint
        ]
        if request.endpoint in public_endpoints:
            return  # Stop processing, allow the request

        # 2. Check for authentication. Everything from here on requires a logged-in user.
        if not current_user.is_authenticated:
            if wants_json():
                return jsonify(error="Authentication required"), 401
            return redirect(url_for('auth.login', next=request.url))

        # 3. Handle developer "super admin" and masquerade logic.
        if getattr(current_user, 'user_type', None) == 'developer':
            selected_org_id = session.get("dev_selected_org_id")
            # If no org selected, redirect to organization selection unless it's a developer-specific or auth permission page
            if not selected_org_id and not (request.path.startswith("/developer/") or request.path.startswith("/auth/permissions")):
                flash("Please select an organization to view customer features.", "warning")
                return redirect(url_for("developer.organizations"))

            # If an org is selected, set it as the effective org for the request
            if selected_org_id:
                from .models import Organization
                from .extensions import db
                g.effective_org = db.session.get(Organization, selected_org_id)
                g.is_developer_masquerade = True
            
            # IMPORTANT: Developers bypass the billing check below.
            return

        # 4. Enforce billing for all regular, authenticated users.
        if current_user.organization and current_user.organization.subscription_tier:
            org = current_user.organization
            tier = org.subscription_tier

            # This is the strict billing logic our tests require.
            if not tier.is_billing_exempt and org.billing_status != 'active':
                # Do not block access to the billing page itself!
                if request.endpoint and not request.endpoint.startswith('billing.'):
                    flash('Your subscription requires attention to continue accessing these features.', 'warning')
                    return redirect(url_for('billing.upgrade'))

        # 5. If all checks pass, do nothing and allow the request to proceed.
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