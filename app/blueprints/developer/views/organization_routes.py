from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import (
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Organization, User
from app.services.developer.organization_service import OrganizationService
from app.services.statistics import AnalyticsDataService

from ..routes import developer_bp


@developer_bp.route("/organizations")
@developer_bp.route("/customer-support")
@login_required
def organizations():
    """Customer support dashboard for organization triage."""
    organizations = OrganizationService.list_all_organizations()
    selected_org_id = session.get("dev_selected_org_id")
    selected_org = OrganizationService.get_selected_organization(selected_org_id)

    dashboard_snapshot = AnalyticsDataService.get_developer_dashboard()
    waitlist_count = dashboard_snapshot.get("waitlist_count", 0)
    attention_orgs = dashboard_snapshot.get("attention_organizations") or []
    attention_org_ids = {org["id"] for org in attention_orgs}
    recent_orgs = dashboard_snapshot.get("recent_organizations") or []

    fault_feed = AnalyticsDataService.get_fault_log_entries(include_all=True)
    support_queue = fault_feed[:8]

    support_metrics = {
        "total_orgs": len(organizations),
        "active_orgs": len([org for org in organizations if org.is_active]),
        "attention_count": len(attention_orgs),
        "waitlist_count": waitlist_count,
        "open_tickets": len(fault_feed),
        "recent_signups": recent_orgs[:5],
    }

    return render_template(
        "developer/customer_support.html",
        organizations=organizations,
        selected_org=selected_org,
        attention_orgs=attention_orgs,
        attention_org_ids=attention_org_ids,
        support_queue=support_queue,
        support_metrics=support_metrics,
        waitlist_count=waitlist_count,
        recent_orgs=recent_orgs[:6],
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Customer Support"},
        ],
    )


@developer_bp.route("/organizations/create", methods=["GET", "POST"])
@login_required
def create_organization():
    """Create new organization with owner user."""
    available_tiers = OrganizationService.build_available_tiers()

    def render_form(form_data=None):
        return render_template(
            "developer/create_organization.html",
            available_tiers=available_tiers,
            form_data=form_data or {},
        )

    if request.method == "POST":
        form_data = request.form
        success, org, message = OrganizationService.create_organization_with_owner(form_data)
        if success and org:
            flash(f'Organization "{org.name}" created successfully', "success")
            return redirect(url_for("developer.organization_detail", org_id=org.id))
        flash(f"Error creating organization: {message}", "error")
        return render_form(form_data)

    return render_form()


@developer_bp.route("/organizations/<int:org_id>")
@login_required
def organization_detail(org_id):
    """Detailed organization management."""
    org = Organization.query.get_or_404(org_id)
    users_query = User.query.filter_by(organization_id=org_id).all()
    tiers_config = OrganizationService.build_tier_config()

    users = []
    for user in users_query:
        users.append(
            {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "user_type": user.user_type,
                "is_organization_owner": user.is_organization_owner,
                "is_active": user.is_active,
                "created_at": user.created_at.strftime("%Y-%m-%d") if user.created_at else None,
                "last_login": user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else None,
                "full_name": user.full_name,
            }
        )

    return render_template(
        "developer/organization_detail.html",
        organization=org,
        users=users,
        users_objects=users_query,
        tiers_config=tiers_config,
        current_tier=org.effective_subscription_tier,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Customer Support", "url": url_for("developer.organizations")},
            {"label": org.name},
        ],
    )


@developer_bp.route("/organizations/<int:org_id>/edit", methods=["POST"])
@login_required
def edit_organization(org_id):
    """Edit organization details."""
    org = Organization.query.get_or_404(org_id)
    success, message = OrganizationService.update_organization(org, request.form)
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.organization_detail", org_id=org_id))


@developer_bp.route("/organizations/<int:org_id>/upgrade", methods=["POST"])
@login_required
def upgrade_organization(org_id):
    """Upgrade organization subscription."""
    org = Organization.query.get_or_404(org_id)
    success, message = OrganizationService.upgrade_organization(org, request.form.get("tier", ""))
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.organization_detail", org_id=org_id))


@developer_bp.route("/organizations/<int:org_id>/delete", methods=["POST"])
@login_required
def delete_organization(org_id):
    """Permanently delete an organization and all associated data."""
    data = request.get_json() or {}
    org = Organization.query.get_or_404(org_id)
    expected_confirm = f"DELETE {org.name}"
    is_valid, message = OrganizationService.validate_deletion(
        data.get("password"), data.get("confirm_text"), expected_confirm
    )
    if not is_valid:
        return jsonify({"success": False, "error": message})

    logging.warning(
        "ORGANIZATION DELETION: Developer %s is deleting organization '%s' (ID: %s) at %s",
        current_user.username,
        org.name,
        org.id,
        datetime.now(timezone.utc),
    )

    success, delete_message = OrganizationService.delete_organization(org)
    if success:
        logging.warning(
            "ORGANIZATION DELETED: '%s' (ID: %s) successfully deleted by developer %s.",
            org.name,
            org_id,
            current_user.username,
        )
        return jsonify({"success": True, "message": delete_message})

    logging.error("ORGANIZATION DELETION FAILED: %s", delete_message)
    return jsonify({"success": False, "error": delete_message})
