"""Billing subscription webhook service.

Synopsis:
Move subscription webhook persistence logic out of route modules so webhook
helpers stay thin and transport-oriented.

Glossary:
- Subscription change: Provider event updating active/past-due/cancelled state.
- Customer id: Provider-side customer identifier linked to an organization.
"""

from __future__ import annotations

from app.extensions import db
from app.models.models import Organization


class SubscriptionWebhookService:
    """Service boundary for subscription webhook organization updates."""

    @staticmethod
    def get_organization_by_customer_id(customer_id: str | None) -> Organization | None:
        if not customer_id:
            return None
        return Organization.query.filter_by(stripe_customer_id=customer_id).first()

    @staticmethod
    def apply_subscription_status(
        organization: Organization, status: str | None
    ) -> None:
        if status in {"active", "trialing"}:
            organization.subscription_status = status
            organization.billing_status = "active"
        elif status == "past_due":
            organization.subscription_status = status
            organization.billing_status = "past_due"
        elif status == "canceled":
            organization.subscription_status = status
            organization.billing_status = "cancelled"
        db.session.commit()

    @staticmethod
    def mark_subscription_cancelled(organization: Organization) -> None:
        organization.subscription_status = "cancelled"
        organization.billing_status = "cancelled"
        db.session.commit()
