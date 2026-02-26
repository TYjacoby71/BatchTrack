"""End-to-end signup checkout flow tests.

Synopsis:
Validates pending signup creation, checkout provisioning, and completion redirect behavior.

Glossary:
- Pending signup: Pre-provision row created before redirecting to checkout.
"""

import os
from types import SimpleNamespace

from app.extensions import db
from app.models.domain_event import DomainEvent
from app.models.pending_signup import PendingSignup
from app.models.subscription_tier import SubscriptionTier
from app.services.billing_service import BillingService
from app.services.signup_checkout_service import (
    SignupCheckoutService,
    SignupRequestContext,
)
from app.services.signup_service import SignupService


# --- Pytest CLI option ---
# Purpose: Allow optional execution against live Stripe credentials.
def pytest_addoption(parser):
    parser.addoption(
        "--stripe-live",
        action="store_true",
        default=False,
        help="Run signup tests against live Stripe (requires env keys)",
    )


class _DummySession:
    """Minimal checkout session stub for non-live test mode."""

    def __init__(self, session_id: str, url: str = "https://stripe.test/checkout"):
        self.id = session_id
        self.url = url


# --- Build fake checkout session ---
# Purpose: Provide webhook-like payload consumed by provisioning logic.
def _make_fake_checkout_session(pending_id: int, customer):
    return SimpleNamespace(
        id=f"cs_test_{pending_id}",
        metadata={"pending_signup_id": str(pending_id)},
        customer_details={
            "email": customer.email,
            "phone": "555-0100",
            "name": f"{customer.first_name} {customer.last_name}",
        },
        customer=customer,
        custom_fields=[
            {"key": "workspace_name", "text": {"value": "Solo Labs"}},
            {"key": "first_name", "text": {"value": customer.first_name}},
            {"key": "last_name", "text": {"value": customer.last_name}},
        ],
        client_reference_id=str(pending_id),
    )


# --- Resolve live mode ---
# Purpose: Enable optional live Stripe checks via marker or CLI switch.
def _use_live_stripe(request):
    marker = request.node.get_closest_marker("stripe_live")
    cli_flag = request.config.getoption("--stripe-live", default=False)
    return bool(marker) or bool(cli_flag)


# --- Require live env keys ---
# Purpose: Fail fast when live mode is requested without Stripe credentials.
def _require_env_keys():
    missing = [
        key
        for key in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")
        if not os.environ.get(key)
    ]
    if missing:
        raise RuntimeError(
            f"--stripe-live requested, but missing env vars: {', '.join(missing)}"
        )


# --- Signup flow test ---
# Purpose: Validate mocked end-to-end signup + Stripe completion orchestration.
def test_signup_flow_end_to_end(app, client, monkeypatch, request):
    live_mode = _use_live_stripe(request)
    if live_mode:
        _require_env_keys()

    with app.app_context():
        solo = SubscriptionTier(
            name="Solo Plan",
            user_limit=1,
            billing_provider="stripe",
            is_customer_facing=True,
            stripe_lookup_key="price_batchtrack_solo",
        )
        db.session.add(solo)
        db.session.commit()

        if not live_mode:

            def fake_checkout(
                tier_obj,
                *,
                customer_email,
                success_url,
                cancel_url,
                metadata,
                client_reference_id=None,
                phone_required=True,
                allow_promo=True,
                existing_customer_id=None,
            ):
                assert tier_obj.id == solo.id
                assert customer_email == "solo@applicant.com"
                assert success_url.endswith("{CHECKOUT_SESSION_ID}")
                assert metadata["tier_id"] == str(solo.id)
                assert phone_required is False
                return _DummySession(f"cs_test_{tier_obj.id}")

            monkeypatch.setattr(
                BillingService, "create_checkout_session_for_tier", fake_checkout
            )

        response = client.post(
            "/auth/signup",
            data={
                "selected_tier": str(solo.id),
                "contact_email": "solo@applicant.com",
                "contact_phone": "555-0100",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        pending = PendingSignup.query.filter_by(email="solo@applicant.com").first()
        assert pending is not None

        if live_mode:
            # End here; webhook + real Stripe finalize the rest.
            return

        # Simulate Stripe webhook success
        fake_customer = SimpleNamespace(
            id="cus_test_123",
            email="solo@applicant.com",
            name="Alex Solo",
            first_name="Alex",
            last_name="Solo",
            metadata={},
        )
        fake_session = _make_fake_checkout_session(pending.id, fake_customer)
        monkeypatch.setattr(
            BillingService, "update_customer_metadata", lambda *args, **kwargs: True
        )

        org, user = BillingService._provision_checkout_session(fake_session)
        assert org and user
        assert pending.status == "account_created"

        # Simulate success route
        def fake_finalize(session_id):
            assert session_id == "cs_live"
            return org, user

        monkeypatch.setattr(BillingService, "finalize_checkout_session", fake_finalize)

        response = client.get(
            "/billing/complete-signup-from-stripe",
            query_string={"session_id": "cs_live"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/onboarding/welcome")
        with client.session_transaction() as sess:
            assert sess.get("_user_id") == str(user.id)
            conversion_payload = sess.get("ga4_checkout_conversion")
            assert isinstance(conversion_payload, dict)
            assert conversion_payload.get("transaction_id") == "cs_live"
            assert conversion_payload.get("tier_id") == str(solo.id)


def test_submission_uses_oauth_prefill_email_when_form_email_missing(app):
    context = SignupRequestContext(
        db_tiers=[],
        available_tiers={},
        lifetime_offers=[],
        lifetime_by_key={},
        lifetime_by_tier_id={},
        has_lifetime_capacity=True,
        signup_source="unit-test",
        referral_code=None,
        promo_code=None,
        preselected_tier="1",
        selected_lifetime_tier="",
        billing_mode="standard",
        standard_billing_cycle="monthly",
        oauth_user_info={"email": "social@example.com"},
        prefill_email="social@example.com",
        prefill_phone="",
    )

    submission = SignupCheckoutService._build_submission(
        context=context,
        form_data={
            "selected_tier": "1",
            "billing_mode": "standard",
            "billing_cycle": "monthly",
            "contact_email": "",
            "contact_phone": "",
        },
    )
    assert submission.contact_email == "social@example.com"


def test_signup_provisioning_prefills_name_and_email_from_oauth_metadata(app):
    with app.app_context():
        tier = SubscriptionTier(
            name="OAuth Tier",
            user_limit=1,
            billing_provider="stripe",
            is_customer_facing=True,
            stripe_lookup_key="price_oauth_tier",
        )
        db.session.add(tier)
        db.session.commit()

        pending = SignupService.create_pending_signup_record(
            tier=tier,
            email="",
            phone=None,
            signup_source="oauth-test",
            referral_code=None,
            promo_code=None,
            detected_timezone="UTC",
            oauth_user_info={
                "oauth_provider": "facebook",
                "oauth_provider_id": "fb_test_id",
            },
            extra_metadata={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "oauth_email": "ada@example.com",
            },
        )

        checkout_session = SimpleNamespace(
            id="cs_test_oauth",
            metadata={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "oauth_email": "ada@example.com",
            },
            customer_details={},
            custom_fields=[],
            client_reference_id=str(pending.id),
        )
        customer = SimpleNamespace(
            id="cus_test_oauth", email=None, phone=None, name=None, metadata={}
        )

        org, user = SignupService.complete_pending_signup_from_checkout(
            pending, checkout_session, customer
        )

        assert org is not None and user is not None
        assert user.email == "ada@example.com"
        assert user.first_name == "Ada"
        assert user.last_name == "Lovelace"
        assert org.contact_email == "ada@example.com"


def test_signup_completion_events_include_code_usage_flags(app):
    with app.app_context():
        tier = SubscriptionTier(
            name="Code Tracking Tier",
            user_limit=1,
            billing_provider="stripe",
            is_customer_facing=True,
            stripe_lookup_key="price_code_tracking",
        )
        db.session.add(tier)
        db.session.commit()

        pending = SignupService.create_pending_signup_record(
            tier=tier,
            email="codeuser@example.com",
            phone=None,
            signup_source="pricing_test",
            referral_code="REF-CODE-1",
            promo_code="SAVE-20",
            detected_timezone="UTC",
            oauth_user_info=None,
            extra_metadata={},
        )

        checkout_session = SimpleNamespace(
            id="cs_test_codes",
            metadata={"pending_signup_id": str(pending.id)},
            customer_details={
                "email": "codeuser@example.com",
                "phone": "555-0101",
                "name": "Casey Coded",
            },
            customer=SimpleNamespace(id="cus_test_codes", metadata={}),
            custom_fields=[],
            client_reference_id=str(pending.id),
        )
        customer = SimpleNamespace(
            id="cus_test_codes",
            email="codeuser@example.com",
            phone="555-0101",
            name="Casey Coded",
            metadata={},
        )

        org, user = SignupService.complete_pending_signup_from_checkout(
            pending, checkout_session, customer
        )
        assert org is not None
        assert user is not None

        for event_name in (
            "account_created",
            "signup_completed",
            "purchase_completed",
        ):
            event = (
                DomainEvent.query.filter_by(event_name=event_name)
                .order_by(DomainEvent.id.desc())
                .first()
            )
            assert event is not None
            props = event.properties or {}
            assert props.get("used_promo_code") is True
            assert props.get("promo_code") == "SAVE-20"
            assert props.get("used_referral_code") is True
            assert props.get("referral_code") == "REF-CODE-1"
