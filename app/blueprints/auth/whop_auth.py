"""Whop authentication helper class.

Synopsis:
Provide helper methods that validate Whop licenses, create/sync users and
organizations, and stash URL-provided license context for login flows.

Glossary:
- Whop license: Access credential validated against Whop API/service.
- Pending license session: Temporary session payload pre-filling login context.
- Organization sync: Process that aligns local org data with Whop entitlements.
"""

import logging

from flask import flash, session

from ...models import User, db
from ...services.whop_service import WhopService

logger = logging.getLogger(__name__)


# --- Whop authentication helper ---
# Purpose: Group Whop login and URL-license processing routines.
# Inputs: License keys, email values, and Flask session context.
# Outputs: User/license payloads after validation and sync operations.
class WhopAuth:
    """Handle Whop-based authentication and signup"""

    # --- Handle Whop login ---
    # Purpose: Validate license/email and return or create matching user.
    # Inputs: License key and email string.
    # Outputs: User model instance or None on validation failure.
    @staticmethod
    def handle_whop_login(license_key, email):
        """Handle login with Whop license key"""
        # Validate license with Whop
        license_data = WhopService.validate_license_key(license_key)
        if not license_data:
            flash("Invalid or expired license key", "error")
            return None

        # Check if email matches
        if license_data["email"] != email:
            flash("Email does not match license key", "error")
            return None

        # Find existing user or create new one
        user = User.query.filter_by(email=email).first()

        if user:
            # Existing user - sync their organization
            if user.organization:
                WhopService.sync_organization_from_whop(
                    user.organization, {**license_data, "license_key": license_key}
                )
            else:
                # User exists but no organization - create one
                organization = WhopService.create_organization_from_whop(
                    license_key, license_data
                )
                user.organization_id = organization.id
                db.session.commit()
        else:
            # New user - create user and organization
            organization = WhopService.create_organization_from_whop(
                license_key, license_data
            )

            user = User(
                email=email,
                username=email.split("@")[0],
                organization_id=organization.id,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

        return user

    # --- Handle license key from URL ---
    # Purpose: Validate URL-provided key and stash pending session data.
    # Inputs: License key string from query parameter.
    # Outputs: License data dict on success, otherwise None.
    @staticmethod
    def handle_license_url(license_key):
        """Handle direct license key from URL parameter"""
        if not license_key:
            return None

        # Validate license
        license_data = WhopService.validate_license_key(license_key)
        if not license_data:
            return None

        # Store license data in session for login form
        session["pending_whop_license"] = {
            "license_key": license_key,
            "email": license_data["email"],
            "tier": license_data["tier"],
        }

        return license_data
