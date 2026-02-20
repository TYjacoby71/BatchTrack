"""Regression tests for analytics registry + relay service."""

from app.models.domain_event import DomainEvent
from app.models.models import Organization, User
from app.services.analytics_event_registry import (
    ANALYTICS_EVENT_REGISTRY,
    CORE_USAGE_EVENT_NAMES,
    required_properties_for,
)
from app.services.analytics_tracking_service import AnalyticsTrackingService


def test_registry_exposes_core_signup_purchase_events():
    for event_name in (
        "signup_completed",
        "signup_checkout_started",
        "signup_checkout_completed",
        "purchase_completed",
    ):
        assert event_name in ANALYTICS_EVENT_REGISTRY

    assert "signup_completed" in CORE_USAGE_EVENT_NAMES
    assert "purchase_completed" in CORE_USAGE_EVENT_NAMES
    assert required_properties_for("signup_completed") == (
        "signup_source",
        "signup_flow",
        "billing_provider",
    )


def test_signup_relay_normalizes_code_usage_payload(app):
    with app.app_context():
        org = Organization.query.first()
        user = User.query.filter_by(organization_id=org.id).first()
        assert org is not None
        assert user is not None

        AnalyticsTrackingService.emit_signup_completed(
            organization_id=org.id,
            user_id=user.id,
            entity_id=org.id,
            signup_source="pricing_page",
            signup_flow="checkout",
            billing_provider="stripe",
            tier_id=123,
            is_oauth_signup=False,
            purchase_completed=True,
            promo_code=" SAVE20 ",
            referral_code="",
        )

        emitted = (
            DomainEvent.query.filter_by(
                event_name="signup_completed",
                organization_id=org.id,
                user_id=user.id,
            )
            .order_by(DomainEvent.id.desc())
            .first()
        )
        assert emitted is not None
        props = emitted.properties or {}
        assert props.get("used_promo_code") is True
        assert props.get("promo_code") == "SAVE20"
        assert props.get("used_referral_code") is False
        assert props.get("referral_code") is None
        assert props.get("purchase_completed") is True


def test_relay_backfills_missing_required_properties(app):
    with app.app_context():
        org = Organization.query.first()
        user = User.query.filter_by(organization_id=org.id).first()
        assert org is not None
        assert user is not None

        AnalyticsTrackingService.emit(
            event_name="signup_checkout_started",
            properties={"tier_id": "1"},
            organization_id=org.id,
            user_id=user.id,
            entity_type="organization",
            entity_id=org.id,
        )

        emitted = (
            DomainEvent.query.filter_by(
                event_name="signup_checkout_started",
                organization_id=org.id,
                user_id=user.id,
            )
            .order_by(DomainEvent.id.desc())
            .first()
        )
        assert emitted is not None
        props = emitted.properties or {}
        assert "billing_mode" in props
        assert "billing_cycle" in props
