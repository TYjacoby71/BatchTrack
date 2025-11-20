import pytest

from app.services.billing_service import BillingService
from app.models import db, SubscriptionTier


@pytest.mark.usefixtures("app")
def test_create_checkout_session_passes_keyword_arguments(app, monkeypatch):
    """BillingService should pass keyword args to StripeService helper."""
    with app.app_context():
        tier = SubscriptionTier(
            name="Pro",
            billing_provider="stripe",
            stripe_lookup_key="price_test",
            user_limit=5,
            is_customer_facing=True,
        )
        db.session.add(tier)
        db.session.commit()

        captured = {}

        class DummySession:
            url = "https://stripe.test/session"

        def fake_create_checkout_session_for_tier(tier_obj, **kwargs):
            captured["tier"] = tier_obj
            captured.update(kwargs)
            return DummySession()

        monkeypatch.setattr(
            "app.services.billing_service.StripeService.create_checkout_session_for_tier",
            fake_create_checkout_session_for_tier,
        )

        session = BillingService.create_checkout_session(
            str(tier.id),
            "owner@example.com",
            "Owner Name",
            "https://app.example.com/billing/success",
            "https://app.example.com/billing/cancel",
            metadata={"source": "upgrade"},
        )

        assert isinstance(session, DummySession)
        assert captured["tier"].id == tier.id
        assert captured["customer_email"] == "owner@example.com"
        assert captured["success_url"] == "https://app.example.com/billing/success"
        assert captured["cancel_url"] == "https://app.example.com/billing/cancel"
        assert captured["metadata"] == {"source": "upgrade"}
