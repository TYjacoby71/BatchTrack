import logging

from flask import flash, session

from ...models import User, db
from ...services.whop_service import WhopService

logger = logging.getLogger(__name__)


class WhopAuth:
    """Handle Whop-based authentication and signup"""

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
