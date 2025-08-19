import os
from flask import request, redirect, url_for, jsonify, session, g, flash
from flask_login import current_user, logout_user
import logging

# Configure logger
logger = logging.getLogger(__name__)

def register_middleware(app):
    """Register all middleware functions with the Flask app."""

    @app.before_request
    def single_security_checkpoint():
        """
        The single, unified security checkpoint for every request.
        Checks are performed in order from least to most expensive.
        """
        # --- DEBUG: Confirm this middleware is executing ---
        print("--- EXECUTING CORRECT MIDDLEWARE ---")

        # 1. Fast-path for completely public endpoints.
        # This is the ONLY list of public routes needed.
        public_endpoints = [
            'static', 'auth.login', 'auth.signup', 'auth.logout',
            'homepage', 'index', 'legal.privacy_policy', 'legal.terms_of_service',
            'billing.webhook'  # Stripe webhook is a critical public endpoint
        ]

        # Pattern-based public paths for flexibility
        public_paths = [
            '/homepage',
            '/legal/',
            '/static/',
            '/auth/login',
            '/auth/signup',
            '/auth/logout'
        ]

        # Check endpoint names first
        if request.endpoint in public_endpoints:
            print(f"MIDDLEWARE DEBUG: Allowing public endpoint: {request.endpoint}")
            return  # Stop processing, allow the request

        # Check path patterns for public access
        for public_path in public_paths:
            if request.path.startswith(public_path):
                print(f"MIDDLEWARE DEBUG: Allowing public path: {request.path}")
                return  # Stop processing, allow the request

        # Debug: Track middleware execution
        print(f"MIDDLEWARE DEBUG: Processing {request.method} {request.path}, endpoint={request.endpoint}")

        # Force reload current_user to ensure fresh session data
        from flask_login import current_user as fresh_current_user

        # Check if user is authenticated
        user_authenticated = hasattr(fresh_current_user, 'is_authenticated') and fresh_current_user.is_authenticated
        print(f"MIDDLEWARE DEBUG: User authenticated={user_authenticated}")

        # 2. Check for authentication. Everything from here on requires a logged-in user.
        if not user_authenticated:
            print(f"MIDDLEWARE DEBUG: User not authenticated, checking if API request")
            # Check if this is an API request (inline to avoid circular imports)
            if (request.is_json or
                request.path.startswith('/api/') or
                'application/json' in request.headers.get('Accept', '') or
                'application/json' in request.headers.get('Content-Type', '')):
                return jsonify(error="Authentication required"), 401
            return redirect(url_for('auth.login', next=request.url))

        # 3. Handle developer "super admin" and masquerade logic.
        if getattr(fresh_current_user, 'user_type', None) == 'developer':
            selected_org_id = session.get("dev_selected_org_id")
            masquerade_org_id = session.get("masquerade_org_id")  # Support both session keys

            # If no org selected, redirect to organization selection unless it's a developer-specific or auth permission page
            if not selected_org_id and not masquerade_org_id and not (request.path.startswith("/developer/") or request.path.startswith("/auth/permissions")):
                flash("Please select an organization to view customer features.", "warning")
                return redirect(url_for("developer.organizations"))

            # If an org is selected, set it as the effective org for the request
            effective_org_id = selected_org_id or masquerade_org_id
            if effective_org_id:
                from .models import Organization
                from .extensions import db
                g.effective_org = db.session.get(Organization, effective_org_id)
                g.is_developer_masquerade = True

            # IMPORTANT: Developers bypass the billing check below.
            return

        # 4. Enforce billing for all regular, authenticated users.
        if fresh_current_user.is_authenticated and getattr(fresh_current_user, 'user_type', None) != 'developer':
            # CRITICAL FIX: Force completely fresh database query to avoid session isolation issues
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

            print(f"DEBUG: User {fresh_current_user.id}, Org billing_status={organization.billing_status if organization else 'NO_ORG'}")

            if organization and organization.subscription_tier:
                tier = organization.subscription_tier
                print(f"DEBUG: Tier exempt={tier.is_billing_exempt}")

                # SIMPLE BILLING LOGIC:
                # If billing bypass is NOT enabled, require active billing status
                if not tier.is_billing_exempt:
                    # Check tier access using unified billing service
                    access_valid, access_reason = BillingService.validate_tier_access(organization)
                    if not access_valid:
                        logger.warning(f"Billing access denied for org {organization.id}: {access_reason}")

                        if access_reason in ['payment_required', 'subscription_canceled']:
                            return redirect(url_for('billing.upgrade'))
                        elif access_reason == 'organization_suspended':
                            flash('Your organization has been suspended. Please contact support.', 'error')
                            logout_user()
                            return redirect(url_for('auth.login'))
                else:
                    print(f"DEBUG: Tier is billing exempt, allowing access")
            else:
                print(f"DEBUG: No org or tier found")

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