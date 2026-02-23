"""System-admin organization management routes.

Synopsis:
Provide admin-only blueprint endpoints for listing organizations and viewing
organization-level user details in the internal administration interface.

Glossary:
- System admin permission: Capability required for privileged admin access.
- Organization detail view: Page showing one organization and related users.
- Admin blueprint: Route namespace mounted under the ``/admin`` URL prefix.
"""

from flask import Blueprint, render_template
from flask_login import login_required

from ...models import Organization, User
from ...utils.permissions import require_permission

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/organizations")
@login_required
@require_permission("dev.system_admin")
def list_organizations():
    """List all organizations for system admin"""
    organizations = Organization.query.all()
    return render_template("admin/organizations.html", organizations=organizations)


@admin_bp.route("/organizations/<int:org_id>")
@login_required
@require_permission("dev.system_admin")
def view_organization(org_id):
    """View specific organization details"""
    org = Organization.query.get_or_404(org_id)
    users = User.query.filter_by(organization_id=org_id).all()
    return render_template(
        "admin/organization_detail.html", organization=org, users=users
    )
