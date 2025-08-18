import os
from flask import request, redirect, url_for, jsonify, session, g, flash
from flask_login import current_user
# Import moved inline to avoid circular imports

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
            'homepage', 'legal.privacy_policy', 'legal.terms_of_service',
            'billing.webhook'  # Stripe webhook is a critical public endpoint
        ]
        if request.endpoint in public_endpoints:
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
            org = fresh_current_user.organization
            
            # This is the most robust way to check, preventing stale data issues.
            if org and org.subscription_tier:
                tier = org.subscription_tier
                
                # This logic is now foolproof:
                # 1. Does the tier REQUIRE a billing check?
                # 2. Is the organization's status something other than 'active'?
                if not tier.is_billing_exempt and org.billing_status != 'active':
                    # Do not block access to the billing page itself!
                    if request.endpoint and not request.endpoint.startswith('billing.'):
                        if request.path.startswith('/api/'):
                            return jsonify({'error': 'Billing issue detected. Please update your payment method.'}), 402
                        else:
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