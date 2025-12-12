"""
Compatibility Stripe service.

Some parts of the app (and tests) expect a lightweight StripeService wrapper.
The canonical billing orchestration lives in `billing_service.py`, but this
module provides the small surface area needed by callers/tests.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import stripe
from flask import current_app


class StripeService:
    @staticmethod
    def initialize_stripe() -> bool:
        """Ensure Stripe API key is configured."""
        secret = None
        try:
            secret = current_app.config.get("STRIPE_SECRET_KEY")
        except Exception:
            secret = None
        secret = secret or os.environ.get("STRIPE_SECRET_KEY")
        if not secret:
            return False
        stripe.api_key = secret
        return True

    @staticmethod
    def get_live_pricing_for_tier(tier_obj) -> Optional[Dict[str, Any]]:
        """Resolve pricing for tier using lookup_key with price_id fallback."""
        lookup_key = getattr(tier_obj, "stripe_lookup_key", None)
        if not lookup_key:
            return None

        if not StripeService.initialize_stripe():
            return None

        # Stripe supports lookup_keys, but some environments store price IDs as lookup keys.
        price_list = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
        price_obj = price_list.data[0] if getattr(price_list, "data", None) else None
        if not price_obj:
            price_obj = stripe.Price.retrieve(lookup_key)

        unit_amount = getattr(price_obj, "unit_amount", None) or 0
        currency = (getattr(price_obj, "currency", None) or "usd").upper()
        recurring = getattr(price_obj, "recurring", None)
        interval = getattr(recurring, "interval", None) if recurring else None
        billing_cycle = "one-time"
        if interval:
            billing_cycle = "yearly" if interval == "year" else "monthly"

        amount = unit_amount / 100
        return {
            "price_id": getattr(price_obj, "id", lookup_key),
            "amount": amount,
            "formatted_price": f"${amount:.0f}",
            "currency": currency,
            "billing_cycle": billing_cycle,
            "lookup_key": lookup_key,
            "last_synced": "now",
        }

    @staticmethod
    def create_checkout_session_for_tier(
        tier_obj,
        *,
        customer_email: str | None,
        customer_name: str | None,  # preserved for API compatibility; Stripe Checkout collects details
        success_url: str,
        cancel_url: str,
        metadata: dict | None = None,
        session_overrides: dict | None = None,
    ):
        """Create a Stripe Checkout Session for a subscription tier."""
        if not StripeService.initialize_stripe():
            return None

        pricing = StripeService.get_live_pricing_for_tier(tier_obj)
        if not pricing:
            return None

        params: Dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": pricing["price_id"], "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {},
        }

        # Caller may supply extra Stripe parameters, but we must not send
        # `customer_update` unless we're attaching to an existing customer.
        if session_overrides:
            params.update(session_overrides)

        if customer_email:
            params["customer_email"] = customer_email
        else:
            # For anonymous checkouts, ask Stripe to create the customer.
            params["customer_creation"] = "always"

        if "customer" not in params and "customer_update" in params:
            params.pop("customer_update", None)

        return stripe.checkout.Session.create(**params)

