"""Auth-facing billing orchestration.

Synopsis:
Centralizes app-access billing checks used by middleware, login, and permission
evaluation so those layers share one policy interpretation.

Glossary:
- Access decision: Canonical allow/upgrade/lock action from policy service.
- Enforcement-exempt route: Route allowed even when upgrade is required.
"""

from __future__ import annotations

from ...billing_access_policy_service import (
    BillingAccessAction,
    BillingAccessPolicyService,
)
from ..core import SubscriptionStanding
from ..helpers import has_valid_tier_integration


class AuthBillingOrchestrator:
    """Single auth billing decision facade."""

    @staticmethod
    def evaluate_organization_access(organization):
        """Return canonical billing-access decision for middleware/login flows."""
        return BillingAccessPolicyService.evaluate_organization(organization)

    @staticmethod
    def is_enforcement_exempt_route(path: str, endpoint: str | None) -> bool:
        """Return whether route bypasses billing redirect enforcement."""
        return BillingAccessPolicyService.is_enforcement_exempt_route(path, endpoint)

    @staticmethod
    def check_subscription_standing(organization) -> tuple[bool, str]:
        """Return tuple matching legacy permission-layer expectations."""
        if not organization:
            standing = SubscriptionStanding(allowed=False, reason="No organization")
            return standing.allowed, standing.reason

        if getattr(organization, "effective_subscription_tier", None) == "exempt":
            standing = SubscriptionStanding(allowed=True, reason="Exempt status")
            return standing.allowed, standing.reason

        tier = getattr(organization, "tier", None) or getattr(
            organization, "subscription_tier_obj", None
        )
        if not tier:
            standing = SubscriptionStanding(
                allowed=False, reason="No subscription tier assigned"
            )
            return standing.allowed, standing.reason

        if not has_valid_tier_integration(organization):
            standing = SubscriptionStanding(
                allowed=False, reason="Subscription tier unavailable"
            )
            return standing.allowed, standing.reason

        decision = BillingAccessPolicyService.evaluate_organization(organization)
        if decision.action == BillingAccessAction.ALLOW:
            standing = SubscriptionStanding(
                allowed=True, reason="Subscription in good standing"
            )
            return standing.allowed, standing.reason
        if decision.action == BillingAccessAction.REQUIRE_UPGRADE:
            standing = SubscriptionStanding(
                allowed=False,
                reason=f"Billing status: {getattr(organization, 'billing_status', '')}",
            )
            return standing.allowed, standing.reason
        standing = SubscriptionStanding(allowed=False, reason="Organization inactive")
        return standing.allowed, standing.reason
