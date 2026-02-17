"""
Characterization tests for signup flow and subscription tier management.

These tests ensure signup bypass flags and tier validation work correctly.
"""

import uuid

from app.extensions import db
from app.models.models import Organization, SubscriptionTier, User
from app.services.signup_service import SignupService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestSignupTierCharacterization:
    """Test current signup and tier behavior to prevent regressions."""

    def test_signup_endpoint_exists(self, app, client):
        """Test that signup endpoint exists."""
        with app.app_context():
            response = client.get("/auth/signup")
            assert response.status_code in [200, 302, 401, 403]

    def test_tier_billing_flags_track_provider(self, app):
        """Ensure billing provider settings drive exemption and integration checks."""
        with app.app_context():
            exempt = SubscriptionTier(name=_unique("Exempt"), billing_provider="exempt")
            paid = SubscriptionTier(
                name=_unique("Paid"),
                billing_provider="stripe",
                stripe_lookup_key=_unique("price_"),
                user_limit=5,
            )
            db.session.add_all([exempt, paid])
            db.session.commit()

            assert exempt.is_billing_exempt is True
            assert exempt.has_valid_integration is True
            assert paid.is_billing_exempt is False
            assert paid.has_valid_integration is True
            assert paid.requires_stripe_billing is True

    def test_find_by_identifier_handles_multiple_keys(self, app):
        """SubscriptionTier.find_by_identifier should support id, name, and lookup keys."""
        with app.app_context():
            tier = SubscriptionTier(
                name=_unique("Team"),
                billing_provider="stripe",
                stripe_lookup_key=_unique("price_team_"),
            )
            db.session.add(tier)
            db.session.commit()

            assert SubscriptionTier.find_by_identifier(str(tier.id)).id == tier.id
            assert SubscriptionTier.find_by_identifier(tier.name.lower()).id == tier.id
            assert (
                SubscriptionTier.find_by_identifier(tier.stripe_lookup_key).id
                == tier.id
            )

    def test_signup_service_creates_pending_signup_record_with_placeholder_email(
        self, app
    ):
        """SignupService should normalize blank emails before redirecting to Stripe."""
        with app.app_context():
            tier = SubscriptionTier(
                name=_unique("Solo"),
                billing_provider="stripe",
                stripe_lookup_key=_unique("price_solo"),
            )
            db.session.add(tier)
            db.session.commit()

            pending = SignupService.create_pending_signup_record(
                tier=tier,
                email="   ",  # intentionally blank
                phone=None,
                signup_source="unit-test",
                referral_code="REF123",
                promo_code=None,
                detected_timezone="America/New_York",
                oauth_user_info={
                    "oauth_provider": "google",
                    "oauth_provider_id": "abc123",
                },
                extra_metadata={"org_name": "Unit Test Co"},
            )

            assert pending.tier_id == tier.id
            assert pending.signup_source == "unit-test"
            assert pending.email.startswith("pending+")
            assert pending.referral_code == "REF123"

    def test_organization_user_limit_respects_tier_configuration(self, app):
        """Organization.can_add_users should respect the active tier's user_limit."""
        with app.app_context():
            tier = SubscriptionTier(name=_unique("SoloLimit"), user_limit=1)
            db.session.add(tier)
            db.session.flush()

            org = Organization(name=_unique("Org"), subscription_tier_id=tier.id)
            db.session.add(org)
            db.session.flush()

            user = User(
                username=_unique("owner"),
                email=_unique("owner") + "@example.com",
                organization_id=org.id,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            fresh_org = db.session.get(Organization, org.id)
            assert fresh_org.can_add_users() is False

            tier.user_limit = -1
            db.session.commit()
            db.session.refresh(fresh_org)
            assert fresh_org.can_add_users() is True
