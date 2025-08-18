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
        # Check for public routes using patterns and specific endpoints
        public_endpoints = [
            'static', 'auth.login', 'auth.signup', 'auth.logout',
            'homepage', 'index', 'legal.privacy_policy', 'legal.terms_of_service',
            'billing.webhook'  # Stripe webhook is a critical public endpoint
        ]

        # Check for public route patterns
        public_patterns = [
            '/static/',     # All static files
            '/legal/',      # All legal pages
            '/homepage',    # Homepage variants
            '/'             # Root homepage
        ]

        # Check for blueprint patterns (if we want to make entire blueprints public)
        public_blueprints = ['legal', 'public']  # Add blueprint names here

        # Check all conditions
        is_public_endpoint = request.endpoint in public_endpoints
        is_public_path = any(request.path.startswith(pattern) for pattern in public_patterns)
        is_public_blueprint = request.endpoint and any(
            request.endpoint.startswith(f'{bp}.') for bp in public_blueprints
        )

        if is_public_endpoint or is_public_path or is_public_blueprint:
            return  # Stop processing, allow the request

        # Debug: Track middleware execution
        print(f"MIDDLEWARE DEBUG: Processing request to {request.path}")
        print(f"MIDDLEWARE DEBUG: Endpoint: {request.endpoint}")
        print(f"MIDDLEWARE DEBUG: Method: {request.method}")
        print(f"MIDDLEWARE DEBUG: User authenticated: {current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else False}")

        # 2. Skip middleware for non-browser requests (API, webhooks, etc.)
        if request.content_type and 'application/json' in request.content_type:
            return

        # 3. Attempt to load the current user
        user = None
        if hasattr(current_user, 'id') and current_user.is_authenticated:
            try:
                user = db.session.get(User, current_user.id)
                print(f"MIDDLEWARE DEBUG: Loaded user {user.id if user else None}")
            except Exception as e:
                print(f"MIDDLEWARE DEBUG: Error loading user: {e}")

        # 4. Developer users can access anything
        if user and user.user_type == 'developer':
            print(f"MIDDLEWARE DEBUG: Developer user {user.id} accessing {request.path}")
            return

        # 5. Check for missing organization (orphaned users)
        if user and not user.organization_id:
            flash('Your account is not associated with an organization. Please contact support.', 'error')
            return redirect(url_for('auth.login'))

        # 6. Handle unauthenticated users
        if not user:
            print(f"MIDDLEWARE DEBUG: No user found, endpoint: {request.endpoint}")
            # For protected pages, redirect to login
            if request.endpoint and not request.endpoint.startswith(('static', 'auth.')):
                return redirect(url_for('auth.login'))
            return

        # 7. Organization-level checks for authenticated users
        org = user.organization
        if not org:
            flash('Organization not found. Please contact support.', 'error')
            return redirect(url_for('auth.login'))

        if not org.is_active:
            flash('Your organization account is currently inactive. Please contact support.', 'warning')
            return redirect(url_for('auth.login'))

        # 2. Check if user is authenticated (this part is for non-public endpoints)
        # This check is now redundant due to earlier checks but kept for clarity of the original flow
        # Force reload current_user to ensure fresh session data
        from flask_login import current_user as fresh_current_user
        user_authenticated = hasattr(fresh_current_user, 'is_authenticated') and fresh_current_user.is_authenticated
        print(f"MIDDLEWARE DEBUG: User authenticated={user_authenticated}")


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

            # Get fresh user and organization data from current session
            fresh_user = db.session.get(User, fresh_current_user.id)
            if fresh_user and fresh_user.organization_id:
                # Force fresh load of organization to get latest billing_status
                org = db.session.get(Organization, fresh_user.organization_id)
            else:
                org = None

            print(f"DEBUG: User {fresh_current_user.id}, Org billing_status={org.billing_status if org else 'NO_ORG'}")

            if org and org.subscription_tier:
                tier = org.subscription_tier
                print(f"DEBUG: Tier exempt={tier.is_billing_exempt}")

                # SIMPLE BILLING LOGIC:
                # If billing bypass is NOT enabled, require active billing status
                if not tier.is_billing_exempt:
                    if org.billing_status not in ['active']:
                        print(f"DEBUG: Billing status '{org.billing_status}' is not active, checking endpoint '{request.endpoint}'")
                        # Do not block access to the billing page itself!
                        if request.endpoint and not request.endpoint.startswith('billing.'):
                            print(f"DEBUG: Blocking access, redirecting to billing")
                            if request.path.startswith('/api/'):
                                return jsonify({'error': 'Billing issue - please contact support'}), 402
                            else:
                                flash('Your subscription requires attention to continue accessing these features.', 'warning')
                                return redirect(url_for('billing.upgrade'))
                        else:
                            print(f"DEBUG: Allowing access to billing endpoint")
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