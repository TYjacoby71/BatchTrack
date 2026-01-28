from __future__ import annotations

from flask import flash, redirect, session, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Organization
from app.utils.timezone_utils import TimezoneUtils

from ..decorators import permission_required
from ..routes import developer_bp


@developer_bp.route("/select-org/<int:org_id>")
@login_required
@permission_required("dev.all_organizations")
def select_organization(org_id):
    """Select an organization to view as developer (customer support)."""
    org = Organization.query.get_or_404(org_id)
    session["dev_selected_org_id"] = org_id
    flash(f"Now viewing data for: {org.name} (Customer Support Mode)", "info")
    return redirect(url_for("app_routes.dashboard"))


@developer_bp.route("/view-as-organization/<int:org_id>")
@login_required
@permission_required("dev.all_organizations")
def view_as_organization(org_id):
    """Set session to view as a specific organization (customer support)."""
    organization = Organization.query.get_or_404(org_id)

    session.pop("dev_selected_org_id", None)
    session.pop("dev_masquerade_context", None)

    session["dev_selected_org_id"] = org_id
    session["dev_masquerade_context"] = {
        "org_name": organization.name,
        "started_at": TimezoneUtils.utc_now().isoformat(),
    }
    session.permanent = True

    flash(f"Now viewing as organization: {organization.name}. Landing on user dashboard.", "info")
    return redirect(url_for("app_routes.dashboard"))


@developer_bp.route("/clear-organization-filter")
@login_required
@permission_required("dev.all_organizations")
def clear_organization_filter():
    """Clear the organization filter and return to developer view."""
    org_name = None
    if "dev_selected_org_id" in session:
        org_id = session["dev_selected_org_id"]
        org = db.session.get(Organization, org_id)
        org_name = org.name if org else "Unknown"

    session.pop("dev_selected_org_id", None)
    session.pop("dev_masquerade_context", None)
    session.pop("dismissed_alerts", None)

    message = "Cleared organization filter and session data"
    if org_name:
        message += f" (was viewing: {org_name})"

    flash(message, "info")
    return redirect(url_for("developer.dashboard"))
