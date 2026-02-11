"""Billing access policy decisions for auth-protected routes.

Synopsis:
Centralizes billing/org-status policy so middleware and auth flows share
the same decision source.

Glossary:
- Recoverable billing state: User should update billing (upgrade page).
- Hard lock state: Organization access is blocked pending support action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .billing_service import BillingService


class BillingAccessAction(str, Enum):
    """Top-level action the caller should take for a request."""

    ALLOW = "allow"
    REQUIRE_UPGRADE = "require_upgrade"
    HARD_LOCK = "hard_lock"


@dataclass(frozen=True)
class BillingAccessDecision:
    """Result of evaluating organization billing access."""

    action: BillingAccessAction
    reason: str
    message: str


class BillingAccessPolicyService:
    """Policy engine for org billing access and route exemptions."""

    _RECOVERY_STATUSES = {"payment_failed", "past_due"}
    _HARD_LOCK_STATUSES = {"suspended", "canceled", "cancelled"}

    @classmethod
    def evaluate_organization(cls, organization) -> BillingAccessDecision:
        """Evaluate a customer's organization and return a policy decision."""
        if not organization:
            return BillingAccessDecision(
                action=BillingAccessAction.ALLOW,
                reason="no_organization",
                message="",
            )

        is_active = bool(getattr(organization, "is_active", True))
        billing_status = (getattr(organization, "billing_status", "active") or "active").lower()
        tier_obj = getattr(organization, "subscription_tier_obj", None)
        tier_is_billing_exempt = bool(getattr(tier_obj, "is_billing_exempt", False))

        if (not is_active) or (billing_status in cls._HARD_LOCK_STATUSES):
            return BillingAccessDecision(
                action=BillingAccessAction.HARD_LOCK,
                reason="organization_inactive",
                message="Your organization is currently inactive. Please contact support immediately.",
            )

        if (not tier_is_billing_exempt) and (billing_status in cls._RECOVERY_STATUSES):
            return BillingAccessDecision(
                action=BillingAccessAction.REQUIRE_UPGRADE,
                reason="billing_required",
                message="Your billing requires attention. Please update your subscription.",
            )

        access_valid, access_reason = BillingService.validate_tier_access(organization)
        if access_valid:
            return BillingAccessDecision(
                action=BillingAccessAction.ALLOW,
                reason=access_reason,
                message="",
            )

        if access_reason == "payment_required":
            return BillingAccessDecision(
                action=BillingAccessAction.REQUIRE_UPGRADE,
                reason=access_reason,
                message="Billing payment is required to continue.",
            )

        if access_reason in {"subscription_canceled", "organization_suspended"}:
            return BillingAccessDecision(
                action=BillingAccessAction.HARD_LOCK,
                reason=access_reason,
                message="Your organization is currently inactive. Please contact support immediately.",
            )

        # Preserve legacy behavior for unknown/non-blocking reasons.
        return BillingAccessDecision(
            action=BillingAccessAction.ALLOW,
            reason=access_reason,
            message="",
        )

    @staticmethod
    def is_enforcement_exempt_route(path: str, endpoint: str | None) -> bool:
        """Return True when billing middleware should not re-redirect this route."""
        if path == "/billing" or path.startswith("/billing/"):
            return True
        if endpoint and endpoint.startswith("billing."):
            return True
        return False
