import logging

import requests
from flask import current_app

from ..models import Organization, SubscriptionTier, db

logger = logging.getLogger(__name__)


class WhopService:
    """Service for handling Whop license validation and integration - STUBBED FOR FUTURE USE"""

    @staticmethod
    def validate_license_key(license_key):
        """Validate a Whop license key and return user/product data"""
        whop_secret = current_app.config.get("WHOP_SECRET_KEY")
        if not whop_secret:
            logger.error("WHOP_SECRET_KEY not configured")
            return None

        try:
            response = requests.get(
                f"https://api.whop.com/v1/licenses/{license_key}",
                headers={"Authorization": f"Bearer {whop_secret}"},
                timeout=10,
            )

            if response.status_code != 200:
                logger.warning(f"Invalid Whop license key: {license_key[:8]}...")
                return None

            data = response.json()

            if data.get("status") != "active":
                logger.warning(f"Inactive Whop license: {license_key[:8]}...")
                return None

            return {
                "tier": WhopService._map_product_to_tier(data["product"]["name"]),
                "email": data["user"]["email"],
                "product_name": data["product"]["name"],
                "user_id": data["user"]["id"],
            }

        except Exception as e:
            logger.error(f"Error validating Whop license: {str(e)}")
            return None

    @staticmethod
    def _map_product_to_tier(product_name):
        """Map Whop product names to BatchTrack tier keys"""
        product_lower = product_name.lower()

        if "lifetime" in product_lower:
            return "lifetime"
        elif "beta" in product_lower:
            return "beta"
        elif "monthly" in product_lower or "maker" in product_lower:
            return "pro"
        elif "team" in product_lower:
            return "team"
        else:
            return "solo"  # Default tier

    @staticmethod
    def sync_organization_from_whop(organization, license_data):
        """Sync organization tier and status from Whop license data"""
        tier_key = license_data["tier"]

        # Map external product tiers to an internal DB tier by name
        tier = SubscriptionTier.query.filter(
            SubscriptionTier.name.ilike(f"%{tier_key}%")
        ).first()

        if tier:
            organization.subscription_tier_id = tier.id
            organization.whop_license_key = license_data.get("license_key")
            organization.whop_product_tier = tier_key
            organization.whop_verified = True
            organization.is_active = True

            db.session.commit()
            logger.info(
                f"Synced organization {organization.id} with Whop tier {tier_key}"
            )

        return tier

    @staticmethod
    def create_organization_from_whop(license_key, license_data):
        """Create a new organization from Whop license data"""
        organization = Organization(
            name=f"{license_data['email'].split('@')[0]} Organization",
            contact_email=license_data["email"],
            whop_license_key=license_key,
            whop_product_tier=license_data["tier"],
            whop_verified=True,
            is_active=True,
        )

        # Assign subscription tier
        tier = SubscriptionTier.query.filter(
            SubscriptionTier.name.ilike(f"%{license_data['tier']}%")
        ).first()
        if tier:
            organization.subscription_tier_id = tier.id

        db.session.add(organization)
        db.session.commit()

        logger.info(f"Created organization {organization.id} from Whop license")
        return organization

    @staticmethod
    def check_whop_access(organization):
        """Check if organization has valid Whop access"""
        if not organization:
            return False, "no_organization"

        if not organization.whop_license_key:
            return False, "no_whop_license"

        if not organization.whop_verified:
            return False, "whop_unverified"

        if not organization.is_active:
            return False, "organization_suspended"

        # Optionally re-validate license periodically
        # For now, trust the stored verification
        return True, "whop_verified"

    @staticmethod
    def get_whop_checkout_url(product_name):
        """Get Whop checkout URL for a product - STUBBED"""
        logger.warning("Whop integration is currently disabled")
        return None

    @staticmethod
    def create_checkout_session(product_id, customer_email, success_url):
        """Create Whop checkout session - STUBBED"""
        logger.warning("Whop checkout is currently disabled")
        return None

    @staticmethod
    def cancel_subscription(license_key):
        """Cancel Whop subscription - STUBBED"""
        logger.warning("Whop subscription management is currently disabled")
        return False

    @staticmethod
    def get_all_available_pricing():
        """Get Whop pricing - STUBBED"""
        logger.warning("Whop pricing is currently disabled")
        return {"tiers": {}, "available": False, "provider": "whop"}
