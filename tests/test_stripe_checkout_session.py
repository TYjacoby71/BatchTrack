from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.billing_service import BillingService
from app.services.lifetime_pricing_service import LifetimePricingService
from app.utils.cache_manager import app_cache


def _pricing_stub(price_id="price_123"):
    return {
        "price_id": price_id,
        "amount": 50,
        "formatted_price": "$50",
        "currency": "USD",
        "billing_cycle": "monthly",
        "lookup_key": price_id,
        "last_synced": "now",
    }


def test_get_live_pricing_falls_back_to_price_id(app):
    tier = SimpleNamespace(id=1, name="Team", stripe_lookup_key="price_fallback")

    price_obj = SimpleNamespace(
        id="price_fallback",
        unit_amount=5000,
        currency="usd",
        active=True,
        recurring=SimpleNamespace(interval="month"),
    )

    with app.app_context(), patch(
        "app.services.billing_service.BillingService.ensure_stripe", return_value=True
    ), patch(
        "app.services.billing_service.stripe.Price.list"
    ) as mock_price_list, patch(
        "app.services.billing_service.stripe.Price.retrieve", return_value=price_obj
    ) as mock_retrieve:

        mock_price_list.return_value = SimpleNamespace(data=[])

        pricing = BillingService.get_live_pricing_for_tier(tier)

        assert pricing["price_id"] == "price_fallback"
        assert pricing["billing_cycle"] == "monthly"
        assert pricing["formatted_price"] == "$50.00"
        mock_price_list.assert_called_once()
        mock_retrieve.assert_called_once_with("price_fallback")


def test_get_live_pricing_treats_12_month_interval_as_yearly(app):
    price_obj = SimpleNamespace(
        id="price_annualized",
        unit_amount=12000,
        currency="usd",
        active=True,
        recurring=SimpleNamespace(interval="month", interval_count=12),
    )

    with app.app_context(), patch(
        "app.services.billing_service.BillingService.ensure_stripe", return_value=True
    ), patch(
        "app.services.billing_service.stripe.Price.list",
        return_value=SimpleNamespace(data=[price_obj]),
    ):
        pricing = BillingService.get_live_pricing_for_lookup_key(
            "batchtrack_team_yearly"
        )
        assert pricing["billing_cycle"] == "yearly"


def test_get_live_pricing_keeps_cents_from_stripe(app):
    price_obj = SimpleNamespace(
        id="price_precise",
        unit_amount=1499,
        currency="usd",
        active=True,
        recurring=SimpleNamespace(interval="month", interval_count=1),
    )

    with app.app_context(), patch(
        "app.services.billing_service.BillingService.ensure_stripe", return_value=True
    ), patch(
        "app.services.billing_service.stripe.Price.list",
        return_value=SimpleNamespace(data=[price_obj]),
    ):
        pricing = BillingService.get_live_pricing_for_lookup_key(
            "batchtrack_precise_monthly"
        )
        assert pricing["amount"] == pytest.approx(14.99)
        assert pricing["formatted_price"] == "$14.99"


def test_checkout_session_drops_customer_update_without_customer(app):
    tier = SimpleNamespace(id=1, name="Team", stripe_lookup_key="price_team")

    with app.app_context(), patch(
        "app.services.billing_service.BillingService.ensure_stripe", return_value=True
    ), patch(
        "app.services.billing_service.BillingService.get_live_pricing_for_lookup_key",
        return_value=_pricing_stub("price_team"),
    ), patch(
        "app.services.billing_service.stripe.checkout.Session.create"
    ) as mock_session_create:

        mock_session_create.return_value = SimpleNamespace(id="cs_test")

        BillingService.create_checkout_session_for_tier(
            tier,
            customer_email=None,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"source": "test"},
            phone_required=False,
        )

        assert mock_session_create.called
        kwargs = mock_session_create.call_args.kwargs
        assert "customer_update" not in kwargs
        assert "customer" not in kwargs
        assert "customer_email" not in kwargs
        assert kwargs["phone_number_collection"] == {"enabled": False}
        assert "custom_fields" not in kwargs


def test_find_related_price_lookup_key_prefers_lookup_key(app):
    base_price = SimpleNamespace(
        id="price_monthly_legacy",
        product="prod_batchtrack_solo",
        recurring=SimpleNamespace(interval="month"),
        active=True,
    )
    yearly_without_lookup = SimpleNamespace(
        id="price_yearly_no_lookup",
        lookup_key=None,
        recurring=SimpleNamespace(interval="year"),
        active=True,
    )
    yearly_with_lookup = SimpleNamespace(
        id="price_yearly_with_lookup",
        lookup_key="batchtrack_solo_yearly",
        recurring=SimpleNamespace(interval="year"),
        active=True,
    )

    with app.app_context(), patch(
        "app.services.billing_service.BillingService.ensure_stripe", return_value=True
    ), patch(
        "app.services.billing_service.BillingService._resolve_price_for_lookup_key",
        return_value=(base_price, "price_id_fallback"),
    ), patch(
        "app.services.billing_service.stripe.Price.list",
        return_value=SimpleNamespace(data=[yearly_without_lookup, yearly_with_lookup]),
    ):

        key = BillingService.find_related_price_lookup_key(
            "price_monthly_legacy", billing_cycle="yearly"
        )
        assert key == "batchtrack_solo_yearly"


def test_find_related_price_lookup_key_accepts_12_month_interval_as_yearly(app):
    base_price = SimpleNamespace(
        id="price_monthly_legacy_two",
        product="prod_batchtrack_fanatic",
        recurring=SimpleNamespace(interval="month", interval_count=1),
        active=True,
    )
    annual_by_month_count = SimpleNamespace(
        id="price_annual_by_month_count",
        lookup_key="batchtrack_fanatic_yearly",
        recurring=SimpleNamespace(interval="month", interval_count=12),
        active=True,
    )

    with app.app_context(), patch(
        "app.services.billing_service.BillingService.ensure_stripe", return_value=True
    ), patch(
        "app.services.billing_service.BillingService._resolve_price_for_lookup_key",
        return_value=(base_price, "price_id_fallback"),
    ), patch(
        "app.services.billing_service.stripe.Price.list",
        return_value=SimpleNamespace(data=[annual_by_month_count]),
    ):

        key = BillingService.find_related_price_lookup_key(
            "price_monthly_legacy_two", billing_cycle="yearly"
        )
        assert key == "batchtrack_fanatic_yearly"


def test_resolve_lookup_variant_falls_back_to_related_product_price(app):
    with app.app_context(), patch.object(
        LifetimePricingService,
        "_resolve_variant_by_product",
        return_value="price_yearly_123",
    ):

        with patch.object(
            LifetimePricingService,
            "_get_lookup_key_pricing",
            side_effect=lambda lookup_key: (
                {"billing_cycle": "yearly"}
                if lookup_key == "price_yearly_123"
                else None
            ),
        ):
            resolved = LifetimePricingService._resolve_lookup_variant(
                base_lookup_key="price_monthly_legacy",
                target_variant="yearly",
                expected_cycle="yearly",
            )
            assert resolved == "price_yearly_123"


def test_get_live_pricing_respects_cached_miss_sentinel(app):
    lookup_key = "missing_lookup_key_cached"
    cache_key = BillingService._pricing_cache_key(lookup_key)

    with app.app_context():
        app_cache.set(cache_key, BillingService._pricing_cache_miss_sentinel, ttl=60)
        with patch(
            "app.services.billing_service.BillingService.ensure_stripe"
        ) as mock_ensure:
            pricing = BillingService.get_live_pricing_for_lookup_key(lookup_key)

    assert pricing is None
    mock_ensure.assert_not_called()


def test_ensure_stripe_applies_network_timeouts_and_retries(app, monkeypatch):
    configured = {}

    class _DummyRequestsClient:
        def __init__(self, timeout, **_kwargs):
            configured["timeout"] = timeout
            self._timeout = timeout

    with app.app_context():
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"
        app.config["STRIPE_HTTP_TIMEOUT_SECONDS"] = 7
        app.config["STRIPE_MAX_NETWORK_RETRIES"] = 0

        monkeypatch.setattr(
            "app.services.billing_service.stripe.default_http_client", None, raising=False
        )
        monkeypatch.setattr(
            "app.services.billing_service.stripe.max_network_retries", 2, raising=False
        )
        monkeypatch.setattr(
            "app.services.billing_service.stripe.RequestsClient",
            _DummyRequestsClient,
            raising=False,
        )

        assert BillingService.ensure_stripe() is True

    assert configured["timeout"] == (3.0, 7.0)


def test_signup_checkout_route_redirects_to_signup_without_session_creation(
    app, monkeypatch
):
    client = app.test_client()

    called = {"value": False}

    def _mark_called(*_args, **_kwargs):
        called["value"] = True
        return None

    monkeypatch.setattr(
        "app.blueprints.auth.signup_routes.SignupCheckoutService.process_submission",
        _mark_called,
    )

    response = client.get(
        "/auth/signup/checkout?tier=3&billing_mode=standard&billing_cycle=monthly&source=pricing_hobbyist_monthly",
        follow_redirects=False,
    )

    assert response.status_code in {301, 302}
    location = response.headers.get("Location") or ""
    assert location.startswith("/signup")
    assert "tier=3" in location
    assert "billing_mode=standard" in location
    assert "billing_cycle=monthly" in location
    assert called["value"] is False
