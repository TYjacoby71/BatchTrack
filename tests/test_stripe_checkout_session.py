from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.stripe_service import StripeService


def _pricing_stub(price_id='price_123'):
    return {
        'price_id': price_id,
        'amount': 50,
        'formatted_price': '$50',
        'currency': 'USD',
        'billing_cycle': 'monthly',
        'lookup_key': price_id,
        'last_synced': 'now'
    }


def test_get_live_pricing_falls_back_to_price_id(app):
    tier = SimpleNamespace(id=1, name='Team', stripe_lookup_key='price_fallback')

    price_obj = SimpleNamespace(
        id='price_fallback',
        unit_amount=5000,
        currency='usd',
        recurring=SimpleNamespace(interval='month')
    )

    with app.app_context(), \
            patch('app.services.stripe_service.StripeService.initialize_stripe', return_value=True), \
            patch('app.services.stripe_service.stripe.Price.list') as mock_price_list, \
            patch('app.services.stripe_service.stripe.Price.retrieve', return_value=price_obj) as mock_retrieve:

        mock_price_list.return_value = SimpleNamespace(data=[])

        pricing = StripeService.get_live_pricing_for_tier(tier)

        assert pricing['price_id'] == 'price_fallback'
        assert pricing['billing_cycle'] == 'monthly'
        mock_price_list.assert_called_once()
        mock_retrieve.assert_called_once_with('price_fallback')


def test_checkout_session_drops_customer_update_without_customer(app):
    tier = SimpleNamespace(id=1, name='Team', stripe_lookup_key='price_team')

    with app.app_context(), \
            patch('app.services.stripe_service.StripeService.initialize_stripe', return_value=True), \
            patch('app.services.stripe_service.StripeService.get_live_pricing_for_tier', return_value=_pricing_stub('price_team')), \
            patch('app.services.stripe_service.stripe.checkout.Session.create') as mock_session_create:

        mock_session_create.return_value = SimpleNamespace(id='cs_test')

        StripeService.create_checkout_session_for_tier(
            tier,
            customer_email=None,
            customer_name=None,
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
            metadata={'source': 'test'},
            session_overrides={'customer_update': {'address': 'auto'}}
        )

        assert mock_session_create.called
        kwargs = mock_session_create.call_args.kwargs
        assert 'customer_update' not in kwargs
        assert kwargs.get('customer_creation') == 'always'
