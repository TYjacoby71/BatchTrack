"""Post-checkout account provisioning orchestration.

Synopsis:
Centralizes Stripe checkout-finalization and conversion payload enrichment used
by billing callback routes.

Glossary:
- Checkout finalization: Resolve provider session into app org/user provisioning.
- Conversion payload: Analytics payload enriched with checkout metadata.
"""

from __future__ import annotations

from ...billing_service import BillingService


class AccountProvisioningOrchestrator:
    """Facade for Stripe signup completion orchestration."""

    @staticmethod
    def finalize_signup_checkout_session(session_id: str):
        return BillingService.finalize_checkout_session(session_id)

    @staticmethod
    def enrich_checkout_conversion_payload(session_id: str, payload: dict) -> dict:
        enriched = dict(payload or {})
        checkout_session = BillingService.get_checkout_session(session_id)
        if checkout_session is None:
            return enriched
        amount_total = getattr(checkout_session, "amount_total", None)
        if amount_total not in (None, ""):
            enriched["value"] = round(float(amount_total) / 100.0, 2)
        currency_code = str(getattr(checkout_session, "currency", "") or "").strip()
        if currency_code:
            enriched["currency"] = currency_code.upper()
        metadata = getattr(checkout_session, "metadata", {}) or {}
        if isinstance(metadata, dict):
            coupon_code = str(metadata.get("promo_code") or "").strip()
            if coupon_code:
                enriched["coupon"] = coupon_code
        return enriched
