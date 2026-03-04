"""Settings-facing billing orchestration.

Synopsis:
Provides billing payloads needed by settings surfaces that handle plan changes,
payment-method management, and add-on purchases.
"""

from __future__ import annotations

from ...billing_service import BillingService
from ..core import BillingSettingsContext


class SettingsBillingOrchestrator:
    """Build billing context for account settings surfaces."""

    @staticmethod
    def build_settings_context(organization) -> BillingSettingsContext:
        pricing_data = BillingService.get_comprehensive_pricing_data()
        return BillingSettingsContext(
            pricing_data=pricing_data,
            has_stripe_customer=(
                bool(getattr(organization, "stripe_customer_id", None))
                if organization
                else False
            ),
            current_tier=(
                BillingService.get_tier_for_organization(organization)
                if organization
                else "exempt"
            ),
        )
