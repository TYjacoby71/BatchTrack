"""Guards against live Stripe lookups on public signup reads."""

from __future__ import annotations

import uuid

import pytest

from app.extensions import db
from app.models.subscription_tier import SubscriptionTier
from app.services.billing_service import BillingService


def _add_public_stripe_tier(app, *, name_prefix: str) -> str:
    """Create a customer-facing Stripe tier and return its name."""
    tier_name = f"{name_prefix}-{uuid.uuid4().hex[:8]}"
    lookup_key = f"guard-{uuid.uuid4().hex[:10]}-monthly"
    with app.app_context():
        tier = SubscriptionTier(
            name=tier_name,
            billing_provider="stripe",
            stripe_lookup_key=lookup_key,
            is_customer_facing=True,
            user_limit=7,
        )
        db.session.add(tier)
        db.session.commit()
    return tier_name


@pytest.mark.usefixtures("app")
def test_signup_page_uses_cache_only_pricing_reads(app, monkeypatch):
    """GET /auth/signup can be forced into cache-only pricing reads."""
    _add_public_stripe_tier(app, name_prefix="Signup Guard Tier")
    observed_network_flags: list[bool] = []

    def _fake_live_pricing_lookup(lookup_key, *, allow_network=True):
        observed_network_flags.append(bool(allow_network))
        return None

    monkeypatch.setattr(
        BillingService,
        "get_live_pricing_for_lookup_key",
        staticmethod(_fake_live_pricing_lookup),
    )
    app.config["SIGNUP_PUBLIC_ALLOW_LIVE_PRICING_NETWORK"] = False

    client = app.test_client()
    response = client.get("/auth/signup")
    assert response.status_code == 200
    assert observed_network_flags, "Expected signup rendering to evaluate pricing keys"
    assert all(
        flag is False for flag in observed_network_flags
    ), "Signup GET must remain cache-only for pricing reads"
    html = response.get_data(as_text=True).lower()
    assert "pricing at secure checkout" in html


@pytest.mark.usefixtures("app")
def test_signup_data_endpoint_uses_cache_only_pricing_reads(app, monkeypatch):
    """GET /auth/signup-data can be forced to avoid live Stripe network calls."""
    tier_name = _add_public_stripe_tier(app, name_prefix="Signup Data Guard Tier")
    observed_network_flags: list[bool] = []

    def _fake_live_pricing_lookup(lookup_key, *, allow_network=True):
        observed_network_flags.append(bool(allow_network))
        return None

    monkeypatch.setattr(
        BillingService,
        "get_live_pricing_for_lookup_key",
        staticmethod(_fake_live_pricing_lookup),
    )
    app.config["SIGNUP_PUBLIC_ALLOW_LIVE_PRICING_NETWORK"] = False

    client = app.test_client()
    response = client.get("/auth/signup-data")
    assert response.status_code == 200
    payload = response.get_json() or {}
    available_tiers = payload.get("available_tiers") or {}
    matching_tier = next(
        (
            tier_data
            for tier_data in available_tiers.values()
            if tier_data.get("name") == tier_name
        ),
        None,
    )
    assert matching_tier is not None
    assert matching_tier.get("monthly_price_display") == (
        "Monthly pricing at secure checkout"
    )
    assert observed_network_flags, "Expected signup-data to evaluate pricing keys"
    assert all(
        flag is False for flag in observed_network_flags
    ), "Signup-data must remain cache-only for pricing reads"


@pytest.mark.usefixtures("app")
def test_signup_page_uses_live_network_pricing_reads_when_enabled(app, monkeypatch):
    """GET /auth/signup should permit live Stripe pricing by default."""
    _add_public_stripe_tier(app, name_prefix="Signup Live Tier")
    observed_network_flags: list[bool] = []

    def _fake_live_pricing_lookup(lookup_key, *, allow_network=True):
        observed_network_flags.append(bool(allow_network))
        return None

    monkeypatch.setattr(
        BillingService,
        "get_live_pricing_for_lookup_key",
        staticmethod(_fake_live_pricing_lookup),
    )
    app.config["SIGNUP_PUBLIC_ALLOW_LIVE_PRICING_NETWORK"] = True

    client = app.test_client()
    response = client.get("/auth/signup")
    assert response.status_code == 200
    assert observed_network_flags, "Expected signup rendering to evaluate pricing keys"
    assert any(
        flag is True for flag in observed_network_flags
    ), "Signup GET should allow live pricing reads when enabled"


@pytest.mark.usefixtures("app")
def test_signup_page_renders_live_pricing_copy_when_enabled(app, monkeypatch):
    """GET /auth/signup should surface formatted live pricing when available."""
    _add_public_stripe_tier(app, name_prefix="Signup Render Tier")

    def _fake_live_pricing_lookup(lookup_key, *, allow_network=True):
        if not allow_network:
            return None
        key = str(lookup_key or "").lower()
        if "yearly" in key:
            return {"formatted_price": "$290.00", "billing_cycle": "yearly"}
        if "lifetime" in key:
            return {"formatted_price": "$990.00", "billing_cycle": "one-time"}
        return {"formatted_price": "$29.00", "billing_cycle": "monthly"}

    monkeypatch.setattr(
        BillingService,
        "get_live_pricing_for_lookup_key",
        staticmethod(_fake_live_pricing_lookup),
    )
    app.config["SIGNUP_PUBLIC_ALLOW_LIVE_PRICING_NETWORK"] = True

    client = app.test_client()
    response = client.get("/auth/signup")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "$29.00" in html
