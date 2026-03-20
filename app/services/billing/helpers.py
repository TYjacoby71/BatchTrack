"""Billing helper utilities.

Synopsis:
Shared helper functions used across billing orchestrators for tier and status
normalization.

Glossary:
- Billing-exempt tier: Tier that bypasses paid-provider standing checks.
- Tier integration: Provider configuration validity for a subscription tier.
"""

from __future__ import annotations


def get_subscription_tier(organization):
    """Return the most reliable tier object available on an organization."""
    if not organization:
        return None
    return getattr(organization, "tier", None) or getattr(
        organization, "subscription_tier_obj", None
    )


def is_billing_exempt_organization(organization) -> bool:
    """Return whether the organization's tier is billing exempt."""
    tier = get_subscription_tier(organization)
    return bool(getattr(tier, "is_billing_exempt", False))


def has_valid_tier_integration(organization) -> bool:
    """Return whether the organization tier has a valid billing integration."""
    tier = get_subscription_tier(organization)
    return bool(getattr(tier, "has_valid_integration", False))


def normalized_billing_status(organization) -> str:
    """Return normalized billing status string."""
    raw = (
        getattr(organization, "billing_status", "active") if organization else "active"
    )
    return str(raw or "active").strip().lower()
