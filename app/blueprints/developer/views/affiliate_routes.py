"""Developer affiliate routes.

Synopsis:
Defines affiliate ecosystem views and payout operations endpoints under the
developer blueprint.
"""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for
from flask_wtf.csrf import validate_csrf

from app.extensions import db
from app.models.models import Organization
from app.services.affiliate import (
    PAYOUT_STATUS_COMPLETE,
    PAYOUT_STATUS_PENDING,
    PAYOUT_STATUS_SENT,
    normalize_payout_status,
)
from app.services.affiliate_service import AffiliateService

from ..decorators import require_developer_permission
from ..routes import developer_bp

logger = logging.getLogger(__name__)


@developer_bp.route("/affiliate-ecosystem")
@require_developer_permission("dev.view_all_billing")
def affiliate_ecosystem():
    """Developer view of cross-organization affiliate health and payouts."""
    page = request.args.get("page", 1, type=int)
    context = AffiliateService.build_developer_ecosystem_context(page=page, per_page=25)
    return render_template(
        "developer/affiliate_ecosystem.html",
        **context,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {
                "label": "Billing Integration",
                "url": url_for("developer.billing_integration"),
            },
            {"label": "Affiliate Ecosystem"},
        ],
    )


@developer_bp.route("/affiliate-ecosystem/organization/<int:org_id>")
@require_developer_permission("dev.view_all_billing")
def affiliate_ecosystem_organization(org_id):
    """Scoped affiliate analytics for one organization."""
    org = db.get_or_404(Organization, org_id)
    affiliate_context = AffiliateService.build_organization_dashboard_context(
        org, page=1, per_page=25
    )
    affiliate_analytics = AffiliateService.build_organization_analytics_context(org)
    return render_template(
        "developer/affiliate_organization_scope.html",
        organization=org,
        affiliate_context=affiliate_context,
        affiliate_analytics=affiliate_analytics,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {
                "label": "Billing Integration",
                "url": url_for("developer.billing_integration"),
            },
            {
                "label": "Affiliate Ecosystem",
                "url": url_for("developer.affiliate_ecosystem"),
            },
            {"label": org.name},
        ],
    )


@developer_bp.route("/affiliate-payouts")
@require_developer_permission("dev.view_all_billing")
def affiliate_payouts():
    """Developer payout operations console for affiliate earnings."""
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", PAYOUT_STATUS_PENDING, type=str)
    organization_query = request.args.get("org", "", type=str)
    organization_id = request.args.get("org_id", type=int)
    context = AffiliateService.build_developer_payout_operations_context(
        page=page,
        per_page=30,
        status_filter=status_filter,
        organization_query=organization_query,
        organization_id=organization_id,
    )
    return render_template(
        "developer/affiliate_payouts.html",
        **context,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {
                "label": "Billing Integration",
                "url": url_for("developer.billing_integration"),
            },
            {"label": "Affiliate Payout Operations"},
        ],
    )


def _affiliate_payout_redirect():
    """Return redirect URL preserving payout list filters."""
    page = request.form.get("return_page", 1, type=int)
    status_filter = request.form.get("return_status", PAYOUT_STATUS_PENDING, type=str)
    organization_query = request.form.get("return_org", "", type=str)
    organization_id = request.form.get("return_org_id", type=int)
    return redirect(
        url_for(
            "developer.affiliate_payouts",
            page=page,
            status=status_filter,
            org=organization_query,
            org_id=organization_id,
        )
    )


def _payout_update_error_message(reason: str | None) -> str:
    """Map payout update error reason to user-facing copy."""
    if reason == "schema_not_ready":
        return "Affiliate payout data is unavailable. Run migrations before updating statuses."
    if reason == "invalid_input":
        return "Missing organization or earning month. Select a payout batch and try again."
    if reason == "invalid_status":
        return "Invalid payout status requested. Use Pending, Sent, Complete, or Unsuccessful."
    if reason == "not_found":
        return "No payout rows were found for the selected organization/month batch."
    if reason == "organization_not_found":
        return "The selected organization no longer exists."
    if reason == "unsupported_payout_provider":
        return (
            "Only Stripe payout destinations are supported for affiliate payout pushes."
        )
    if reason == "payout_account_not_ready":
        return "Stripe payout destination is not configured for this organization."
    if reason == "not_eligible":
        return "This batch is still in arrears and is not eligible yet. Use force push to override."
    if reason == "blocked_by_churn_window":
        return "This batch was blocked by churn within the 30-day arrears window."
    if reason == "no_payable_rows":
        return "No payable earnings were found in this batch."
    if reason == "stripe_not_configured":
        return "Stripe is not configured on this environment."
    if reason == "stripe_transfer_failed":
        return (
            "Stripe payout push failed. Check payout destination and platform balance."
        )
    return "Unable to update payout status due to an unexpected error."


def _parse_force_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@developer_bp.route("/affiliate-payouts/update-status", methods=["POST"])
@require_developer_permission("dev.view_all_billing")
def affiliate_payout_update_status():
    """Update payout status for all earnings in an org-month batch."""
    try:
        validate_csrf(request.form.get("csrf_token"))
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/developer/views/affiliate_routes.py:csrf",
            exc_info=True,
        )
        flash(
            "Security validation failed while updating payout status. Refresh and try again.",
            "error",
        )
        return _affiliate_payout_redirect()

    organization_id = request.form.get("organization_id", type=int)
    earning_month = request.form.get("earning_month", type=str)
    target_status = normalize_payout_status(request.form.get("target_status", type=str))
    payout_reference = request.form.get("payout_reference", type=str)
    result = AffiliateService.update_monthly_earnings_status(
        organization_id=organization_id,
        earning_month=earning_month,
        target_status=target_status,
        payout_reference=payout_reference,
        auto_commit=True,
    )
    if not result.get("ok"):
        flash(_payout_update_error_message(result.get("reason")), "error")
        return _affiliate_payout_redirect()

    status_changed_rows = int(result.get("status_changed_rows", 0) or 0)
    updated_rows = int(result.get("updated_rows", 0) or 0)
    changed_commission_cents = int(
        result.get("status_changed_commission_cents", 0) or 0
    )
    status_label = result.get("target_status_label") or "Updated"
    if status_changed_rows > 0:
        flash(
            (
                f"Updated {status_changed_rows} earning row(s) to {status_label} "
                f"for {result.get('earning_month')} "
                f"({AffiliateService._format_currency_cents(changed_commission_cents)})."
            ),
            "success",
        )
        notification = AffiliateService.notify_payout_status_update(
            organization_id=organization_id,
            earning_month=result.get("earning_month_date"),
            payout_status=result.get("target_status"),
            commission_amount_cents=changed_commission_cents,
            updated_rows=status_changed_rows,
            payout_reference=(payout_reference or "").strip() or None,
            referrer_user_ids=result.get("referrer_user_ids") or [],
        )
        attempted = int(notification.get("attempted", 0) or 0)
        sent = int(notification.get("sent", 0) or 0)
        if attempted == 0:
            flash(
                "Payout status updated, but no recipient email was available for notification.",
                "info",
            )
        elif sent < attempted:
            flash(
                f"Payout status updated, but only {sent}/{attempted} notification emails were sent from noreply.",
                "warning",
            )
    elif updated_rows > 0 and target_status in {
        PAYOUT_STATUS_SENT,
        PAYOUT_STATUS_COMPLETE,
    }:
        flash("Payout reference updated for the selected payout batch.", "success")
    else:
        flash(
            "No payout rows changed. The selected batch is already in that status.",
            "info",
        )
    return _affiliate_payout_redirect()


@developer_bp.route("/affiliate-payouts/push-stripe", methods=["POST"])
@require_developer_permission("dev.view_all_billing")
def affiliate_payout_push_stripe():
    """Push a payout batch to Stripe and mark it as sent."""
    try:
        validate_csrf(request.form.get("csrf_token"))
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/developer/views/affiliate_routes.py:csrf_push",
            exc_info=True,
        )
        flash(
            "Security validation failed while pushing payout. Refresh and try again.",
            "error",
        )
        return _affiliate_payout_redirect()

    organization_id = request.form.get("organization_id", type=int)
    earning_month = request.form.get("earning_month", type=str)
    force_push = _parse_force_flag(request.form.get("force_push", type=str))
    result = AffiliateService.push_monthly_payout_to_stripe(
        organization_id=organization_id,
        earning_month=earning_month,
        force=force_push,
        auto_commit=True,
        send_email=True,
    )
    if not result.get("ok"):
        message = _payout_update_error_message(result.get("reason"))
        if result.get("reason") == "not_eligible" and result.get("eligible_on"):
            message = (
                f"Batch is in arrears until {result.get('eligible_on')} "
                f"({result.get('days_until_eligible')} day(s) remaining)."
            )
        flash(message, "error")
        return _affiliate_payout_redirect()

    flash(
        (
            f"Stripe payout pushed as Sent for {result.get('earning_month')} "
            f"({AffiliateService._format_currency_cents(result.get('status_changed_commission_cents'))})."
        ),
        "success",
    )
    payout_reference = result.get("payout_reference")
    if payout_reference:
        flash(f"Payout reference: {payout_reference}", "info")

    blocked_rows = int(result.get("blocked_rows", 0) or 0)
    if blocked_rows > 0:
        flash(
            (
                f"Skipped {blocked_rows} earning row(s) due to churn inside the "
                f"{AffiliateService.PAYOUT_ARREARS_DAYS}-day hold window."
            ),
            "warning",
        )
    email_attempted = int(result.get("email_attempted", 0) or 0)
    email_sent = int(result.get("email_sent", 0) or 0)
    if email_attempted == 0:
        flash(
            "Stripe payout was pushed, but no recipient email was available for status notification.",
            "info",
        )
    elif email_sent < email_attempted:
        flash(
            f"Stripe payout pushed, but only {email_sent}/{email_attempted} notification emails were sent from noreply.",
            "warning",
        )
    return _affiliate_payout_redirect()


@developer_bp.route("/affiliate-payouts/run-auto", methods=["POST"])
@require_developer_permission("dev.view_all_billing")
def affiliate_payout_run_auto():
    """Run auto payout processing for eligible arrears batches."""
    try:
        validate_csrf(request.form.get("csrf_token"))
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/developer/views/affiliate_routes.py:csrf_auto",
            exc_info=True,
        )
        flash(
            "Security validation failed while running auto payouts. Refresh and try again.",
            "error",
        )
        return _affiliate_payout_redirect()

    result = AffiliateService.run_automatic_stripe_payouts(
        limit_batches=50, auto_commit=True
    )
    if not result.get("ok"):
        flash(_payout_update_error_message(result.get("reason")), "error")
        return _affiliate_payout_redirect()

    flash(
        (
            f"Auto payout run complete: {result.get('sent_batches')} batch(es) pushed, "
            f"{result.get('skipped_not_eligible')} not yet eligible, "
            f"{result.get('skipped_no_payable')} without payable rows, "
            f"{result.get('failed_batches')} failed."
        ),
        "success",
    )
    if int(result.get("sent_batches", 0) or 0) > 0:
        flash(
            f"Auto-pushed payout total: {result.get('sent_commission_display')}.",
            "info",
        )
    return _affiliate_payout_redirect()


__all__ = [
    "affiliate_ecosystem",
    "affiliate_ecosystem_organization",
    "affiliate_payouts",
    "affiliate_payout_push_stripe",
    "affiliate_payout_run_auto",
    "affiliate_payout_update_status",
]
