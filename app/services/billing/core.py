"""Billing core domain models.

Synopsis:
Provides lightweight shared data shapes for billing orchestrators.

Glossary:
- Subscription standing: Boolean access verdict plus reason string.
- Settings context: Normalized billing payload for settings templates.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionStanding:
    """Boolean access standing plus explanation."""

    allowed: bool
    reason: str


@dataclass(frozen=True)
class BillingSettingsContext:
    """Settings billing payload normalized for template consumption."""

    pricing_data: dict
    has_stripe_customer: bool
    current_tier: str

    def as_dict(self) -> dict:
        return {
            "pricing_data": self.pricing_data,
            "has_stripe_customer": self.has_stripe_customer,
            "current_tier": self.current_tier,
        }
