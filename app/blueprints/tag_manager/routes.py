"""Tag-management blueprint routes.

Synopsis:
Expose authenticated UI and CRUD API endpoints for organization-scoped tags
used by inventory and workflow categorization features.

Glossary:
- Tag manager: Web interface for creating and editing reusable tags.
- Scoped query: Organization-filtered model query protecting tenant isolation.
- Soft delete: Deactivation flow that marks tag records inactive.
"""

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.services.tag_manager_service import TagManagerService
from app.utils.permissions import require_permission

# --- Tag manager blueprint ---
# Purpose: Group organization-scoped tag-management routes.
# Inputs: None.
# Outputs: Flask blueprint instance for tag endpoints.
tag_manager_bp = Blueprint("tag_manager", __name__)


# --- Render tag manager page ---
# Purpose: Show the authenticated tag-management interface.
# Inputs: Logged-in user with tags.manage permission.
# Outputs: Rendered template populated with scoped tag records.
@tag_manager_bp.route("/tag-manager")
@login_required
@require_permission("tags.manage")
def tag_manager():
    tags = TagManagerService.list_tags()
    return render_template("tag_manager.html", tags=tags)


# --- List active tags ---
# Purpose: Return active tags for current organization as JSON.
# Inputs: Authenticated request with tags.manage permission.
# Outputs: JSON array of active tag metadata.
@tag_manager_bp.route("/api/tags", methods=["GET"])
@login_required
@require_permission("tags.manage")
def get_tags():
    tags = TagManagerService.list_tags(active_only=True)
    return jsonify(
        [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
            }
            for tag in tags
        ]
    )


# --- Create tag ---
# Purpose: Persist a new organization-scoped tag from JSON payload.
# Inputs: Tag name plus optional color/description fields.
# Outputs: JSON success response with created tag id.
@tag_manager_bp.route("/api/tags", methods=["POST"])
@login_required
@require_permission("tags.manage")
def create_tag():
    data = request.get_json()

    tag = TagManagerService.create_tag(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        name=data["name"],
        color=data.get("color", "#6c757d"),
        description=data.get("description", ""),
    )

    return jsonify({"success": True, "tag_id": tag.id})


# --- Update tag ---
# Purpose: Modify an existing organization-scoped tag.
# Inputs: Tag id path parameter and updated JSON field values.
# Outputs: JSON success indicator after commit.
@tag_manager_bp.route("/api/tags/<int:tag_id>", methods=["PUT"])
@login_required
@require_permission("tags.manage")
def update_tag(tag_id):
    tag = TagManagerService.get_tag_or_404(tag_id)
    data = request.get_json()

    TagManagerService.update_tag(
        tag,
        name=data["name"],
        color=data.get("color", tag.color),
        description=data.get("description", tag.description),
    )

    return jsonify({"success": True})


# --- Soft delete tag ---
# Purpose: Deactivate a tag without removing the database row.
# Inputs: Tag id path parameter.
# Outputs: JSON success indicator after deactivation.
@tag_manager_bp.route("/api/tags/<int:tag_id>", methods=["DELETE"])
@login_required
@require_permission("tags.manage")
def delete_tag(tag_id):
    tag = TagManagerService.get_tag_or_404(tag_id)
    TagManagerService.soft_delete_tag(tag)

    return jsonify({"success": True})
