"""Affiliate payout status email notifications.

Synopsis:
Composes and sends payout batch status update emails to organization recipients.
"""

from __future__ import annotations

from datetime import date

from ...extensions import db
from ...models import User
from ..email_service import EmailService
from .payout_status import payout_status_label


class AffiliatePayoutNotificationService:
    """Dispatch payout-status update notifications."""

    @staticmethod
    def _collect_recipients(
        organization, referrer_user_ids: list[int] | None = None
    ) -> list[str]:
        recipients: list[str] = []
        if organization is None:
            return recipients

        owner = getattr(organization, "owner", None)
        owner_email = (getattr(owner, "email", "") or "").strip().lower()
        if owner_email:
            recipients.append(owner_email)

        contact_email = (
            (getattr(organization, "contact_email", "") or "").strip().lower()
        )
        if contact_email and contact_email not in recipients:
            recipients.append(contact_email)

        for user_id in referrer_user_ids or []:
            user = db.session.get(User, int(user_id))
            if not user:
                continue
            user_email = (getattr(user, "email", "") or "").strip().lower()
            if user_email and user_email not in recipients:
                recipients.append(user_email)
        return recipients

    @classmethod
    def send_payout_status_update_email(
        cls,
        *,
        organization,
        earning_month: date | None,
        payout_status: str,
        commission_amount_cents: int,
        updated_rows: int,
        payout_reference: str | None = None,
        referrer_user_ids: list[int] | None = None,
    ) -> dict[str, int]:
        """Send payout status update notifications and return send counters."""
        recipients = cls._collect_recipients(
            organization=organization,
            referrer_user_ids=referrer_user_ids,
        )
        if not recipients:
            return {"attempted": 0, "sent": 0}

        month_label = (
            earning_month.strftime("%B %Y")
            if isinstance(earning_month, date)
            else "selected month"
        )
        status_label = payout_status_label(payout_status)
        organization_name = getattr(organization, "name", "your organization")
        commission_display = f"${int(commission_amount_cents or 0) / 100:,.2f}"
        reference_line = (
            f"<p><strong>Payout reference:</strong> {payout_reference}</p>"
            if payout_reference
            else ""
        )
        text_reference_line = (
            f"Payout reference: {payout_reference}\n" if payout_reference else ""
        )

        subject = f"Affiliate payout update: {status_label} ({month_label})"
        html_body = f"""
        <h3>Affiliate payout status updated</h3>
        <p>Your affiliate payout batch for <strong>{organization_name}</strong> has been updated.</p>
        <p><strong>Month:</strong> {month_label}<br>
        <strong>Status:</strong> {status_label}<br>
        <strong>Commission total:</strong> {commission_display}<br>
        <strong>Updated entries:</strong> {int(updated_rows or 0)}</p>
        {reference_line}
        <p>This message was sent from the BatchTrack no-reply mailbox.</p>
        """
        text_body = (
            "Affiliate payout status updated\n\n"
            f"Organization: {organization_name}\n"
            f"Month: {month_label}\n"
            f"Status: {status_label}\n"
            f"Commission total: {commission_display}\n"
            f"Updated entries: {int(updated_rows or 0)}\n"
            f"{text_reference_line}\n"
            "This message was sent from the BatchTrack no-reply mailbox.\n"
        )

        sent_count = 0
        for recipient in recipients:
            if EmailService._send_email(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            ):
                sent_count += 1
        return {"attempted": len(recipients), "sent": sent_count}
