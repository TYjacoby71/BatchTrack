
import os
from flask import request, redirect, url_for, jsonify, session, g, flash
from flask_login import current_user
from .extensions import login_manager
from .utils.http import wants_json

def register_middleware(app):
    """Register all application middleware"""
    
    @app.before_request
    def _global_login_gate():
        """Unified authentication and authorization gate"""
        # Fast-path public endpoints
        public = {
            "static", "auth.login", "auth.logout", "auth.signup",
            "billing.webhooks", "homepage"
        }
        if request.endpoint and any([
            request.endpoint in public,
            request.path.startswith("/static/"),
            request.path.startswith("/billing/webhooks/"),
            request.path.startswith("/api/waitlist"),
            request.path in ("/", "/homepage"),
        ]):
            return

        # Test bypass for inventory adjust (matches current behavior)
        if app.config.get("TESTING") and request.path.startswith("/inventory/adjust"):
            return

        # Require authentication
        if not current_user.is_authenticated:
            if wants_json():
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for('auth.login'))

        # Handle developer masquerade
        if current_user.user_type == "developer":
            if request.path.startswith("/developer/") or request.path.startswith("/auth/"):
                return
            selected_org_id = session.get("dev_selected_org_id")
            if not selected_org_id:
                if wants_json():
                    return jsonify({"error": "Developer must select organization"}), 403
                flash("Please select an organization to access customer features", "warning")
                return redirect(url_for("developer.organizations"))

            from .models import Organization
            selected_org = Organization.query.get(selected_org_id)
            if not selected_org:
                session.pop("dev_selected_org_id", None)
                flash("Selected organization no longer exists", "error")
                return redirect(url_for("developer.organizations"))

            # Set masquerade context
            g.effective_org_id = selected_org_id
            g.effective_org = selected_org
            g.is_developer_masquerade = True

        elif not current_user.organization_id:
            if wants_json():
                return jsonify({"error": "No organization context"}), 403
            flash("No organization context available", "error")
            return redirect(url_for("auth.logout"))

    @app.before_request
    def _force_https_in_prod():
        """Force HTTPS in production"""
        if (
            os.environ.get("REPLIT_DEPLOYMENT") == "true"
            and not request.is_secure
            and request.headers.get("X-Forwarded-Proto") != "https"
            and request.url.startswith("http://")
        ):
            return redirect(request.url.replace("http://", "https://"), code=301)

    @app.before_request
    def _enforce_billing_access():
        """Enforce billing access requirements"""
        if (request.endpoint and (
            request.endpoint.startswith('static') or
            request.endpoint.startswith('auth.') or
            request.endpoint.startswith('billing.')
        )):
            return

        if current_user.is_authenticated and current_user.organization:
            from .utils.authorization import AuthorizationHierarchy
            has_access, reason = AuthorizationHierarchy.check_organization_access(current_user.organization)
            if not has_access:
                if reason == 'organization_suspended':
                    flash('Your organization has been suspended. Please contact support.', 'error')
                    return redirect(url_for('billing.upgrade'))
                elif reason not in ['exempt', 'developer']:
                    flash('Subscription required to access the system.', 'error')
                    return redirect(url_for('billing.upgrade'))

    @app.after_request
    def _security_headers(resp):
        """Add security headers in production"""
        if os.environ.get("REPLIT_DEPLOYMENT") == "true":
            resp.headers.update({
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
            })
        return resp
