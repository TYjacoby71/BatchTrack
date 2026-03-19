"""Module documentation.

Synopsis:
This module defines route handlers and helpers for `app/blueprints/developer/views/organization_routes.py`.

Glossary:
- Route handler: A Flask view function bound to an endpoint.
- Helper unit: A module-level function or class supporting route/service flow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import Organization, User
from app.services.developer.organization_service import OrganizationService
from app.services.statistics import AnalyticsDataService
from app.services.tools.feedback_note_service import ToolFeedbackNoteService

from ..decorators import require_developer_permission
from ..routes import developer_bp


def _feedback_flow_sort_key(flow_key: str) -> int:
    try:
        return ToolFeedbackNoteService.FLOW_ORDER.index(flow_key)
    except ValueError:
        return len(ToolFeedbackNoteService.FLOW_ORDER)


# --- Organizations ---
# Purpose: Define the top-level behavior of `organizations` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/organizations")
@developer_bp.route("/customer-support")
@require_developer_permission("dev.all_organizations")
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


# --- Support Feedback Submissions ---
# Purpose: Define the top-level behavior of `support_submissions` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/support-submissions")
@require_developer_permission("dev.all_organizations")
def support_submissions():
    """View customer feedback-note submissions grouped by source and type."""
    refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    global_index = ToolFeedbackNoteService.load_global_index(refresh=refresh)
    raw_sources = global_index.get("sources") if isinstance(global_index, dict) else []
    if not isinstance(raw_sources, list):
        raw_sources = []

    source_rows: list[dict] = []
    feedback_total_count = 0
    for source_row in raw_sources:
        if not isinstance(source_row, dict):
            continue
        source_key = ToolFeedbackNoteService.normalize_source(source_row.get("source"))
        raw_flows = source_row.get("flows")
        if not isinstance(raw_flows, list):
            continue

        flows: list[dict] = []
        source_total = 0
        for flow_row in raw_flows:
            if not isinstance(flow_row, dict):
                continue
            flow_key = ToolFeedbackNoteService.normalize_flow(flow_row.get("flow"))
            if not flow_key:
                continue

            try:
                count = int(flow_row.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            source_total += max(count, 0)
            flows.append(
                {
                    "flow": flow_key,
                    "flow_label": str(
                        flow_row.get("flow_label")
                        or ToolFeedbackNoteService.FLOW_LABELS.get(
                            flow_key, flow_key.replace("_", " ").title()
                        )
                    ),
                    "count": max(count, 0),
                }
            )

        if not flows:
            continue

        flows.sort(key=lambda row: _feedback_flow_sort_key(row["flow"]))
        source_rows.append(
            {
                "source": source_key,
                "source_label": source_key.replace("_", " ").replace("-", " ").title(),
                "flows": flows,
                "total_count": source_total,
            }
        )
        feedback_total_count += source_total

    source_rows.sort(key=lambda row: (-row["total_count"], row["source_label"]))

    requested_source = request.args.get("source")
    selected_source_key = (
        ToolFeedbackNoteService.normalize_source(requested_source)
        if requested_source
        else None
    )
    selected_source = next(
        (
            row
            for row in source_rows
            if selected_source_key and row["source"] == selected_source_key
        ),
        None,
    )
    if selected_source is None and source_rows:
        selected_source = source_rows[0]
        selected_source_key = selected_source["source"]

    requested_flow = request.args.get("flow")
    selected_flow_key = (
        ToolFeedbackNoteService.normalize_flow(requested_flow)
        if requested_flow
        else None
    )
    if selected_source:
        available_flows = [flow["flow"] for flow in selected_source["flows"]]
        if selected_flow_key not in available_flows:
            selected_flow_key = available_flows[0] if available_flows else None

    selected_bucket = None
    selected_entries: list[dict] = []
    if selected_source_key and selected_flow_key:
        selected_bucket = ToolFeedbackNoteService.load_bucket(
            source=selected_source_key, flow=selected_flow_key, limit=250
        )
        selected_entries = selected_bucket.get("entries") or []

    return render_template(
        "developer/support_submissions.html",
        feedback_sources=source_rows,
        feedback_source_count=len(source_rows),
        feedback_total_count=feedback_total_count,
        selected_feedback_source=selected_source,
        selected_feedback_flow=selected_flow_key,
        selected_feedback_bucket=selected_bucket,
        selected_feedback_entries=selected_entries,
        generated_at=(
            global_index.get("updated_at") if isinstance(global_index, dict) else None
        ),
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Customer Support", "url": url_for("developer.organizations")},
            {"label": "Support Submissions"},
        ],
    )


# --- Create Organization ---
# Purpose: Define the top-level behavior of `create_organization` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/organizations/create", methods=["GET", "POST"])
@require_developer_permission("dev.create_organizations")
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
        success, org, message = OrganizationService.create_organization_with_owner(
            form_data
        )
        if success and org:
            flash(f'Organization "{org.name}" created successfully', "success")
            return redirect(url_for("developer.organization_detail", org_id=org.id))
        flash(f"Error creating organization: {message}", "error")
        return render_form(form_data)

    return render_form()


# --- Organization Detail ---
# Purpose: Define the top-level behavior of `organization_detail` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/organizations/<int:org_id>")
@require_developer_permission("dev.all_organizations")
def organization_detail(org_id):
    """Detailed organization management."""
    org = db.get_or_404(Organization, org_id)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = max(10, min(per_page, 200))
    search = (request.args.get("search") or "").strip()

    base_query = User.query.filter_by(organization_id=org_id)
    users_query = base_query

    if search:
        term = f"%{search}%"
        users_query = users_query.filter(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
                User.first_name.ilike(term),
                User.last_name.ilike(term),
            )
        )

    users_query = users_query.order_by(User.created_at.desc())
    users_pagination = users_query.paginate(
        page=page, per_page=per_page, error_out=False
    )

    total_users = base_query.count()
    active_users_count = base_query.filter_by(is_active=True).count()

    tiers_config = OrganizationService.build_tier_config()

    return render_template(
        "developer/organization_detail.html",
        organization=org,
        users_objects=users_pagination.items,
        users_pagination=users_pagination,
        users_total=total_users,
        users_active_count=active_users_count,
        search=search,
        per_page=per_page,
        tiers_config=tiers_config,
        current_tier=org.effective_subscription_tier,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Customer Support", "url": url_for("developer.organizations")},
            {"label": org.name},
        ],
    )


# --- Edit Organization ---
# Purpose: Define the top-level behavior of `edit_organization` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/organizations/<int:org_id>/edit", methods=["POST"])
@require_developer_permission("dev.modify_any_organization")
def edit_organization(org_id):
    """Edit organization details."""
    org = db.get_or_404(Organization, org_id)
    success, message = OrganizationService.update_organization(org, request.form)
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.organization_detail", org_id=org_id))


# --- Upgrade Organization ---
# Purpose: Define the top-level behavior of `upgrade_organization` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/organizations/<int:org_id>/upgrade", methods=["POST"])
@require_developer_permission("dev.billing_override")
def upgrade_organization(org_id):
    """Upgrade organization subscription."""
    org = db.get_or_404(Organization, org_id)
    success, message = OrganizationService.upgrade_organization(
        org, request.form.get("tier", "")
    )
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.organization_detail", org_id=org_id))


# --- Delete Organization ---
# Purpose: Define the top-level behavior of `delete_organization` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/organizations/<int:org_id>/delete", methods=["POST"])
@require_developer_permission("dev.delete_organizations")
def delete_organization(org_id):
    """Permanently delete an organization and all associated data."""
    data = request.get_json() or {}
    org = db.get_or_404(Organization, org_id)
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
