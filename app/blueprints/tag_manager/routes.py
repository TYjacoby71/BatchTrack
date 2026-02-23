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

from app.models import Tag, db
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
    tags = Tag.scoped().all()
    return render_template("tag_manager.html", tags=tags)


# --- List active tags ---
# Purpose: Return active tags for current organization as JSON.
# Inputs: Authenticated request with tags.manage permission.
# Outputs: JSON array of active tag metadata.
@tag_manager_bp.route("/api/tags", methods=["GET"])
@login_required
@require_permission("tags.manage")
def get_tags():
    tags = Tag.scoped().filter_by(is_active=True).all()
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

    tag = Tag(
        name=data["name"],
        color=data.get("color", "#6c757d"),
        description=data.get("description", ""),
        organization_id=current_user.organization_id,
        created_by=current_user.id,
    )

    db.session.add(tag)
    db.session.commit()

    return jsonify({"success": True, "tag_id": tag.id})


# --- Update tag ---
# Purpose: Modify an existing organization-scoped tag.
# Inputs: Tag id path parameter and updated JSON field values.
# Outputs: JSON success indicator after commit.
@tag_manager_bp.route("/api/tags/<int:tag_id>", methods=["PUT"])
@login_required
@require_permission("tags.manage")
def update_tag(tag_id):
    tag = Tag.scoped().filter_by(id=tag_id).first_or_404()
    data = request.get_json()

    tag.name = data["name"]
    tag.color = data.get("color", tag.color)
    tag.description = data.get("description", tag.description)

    db.session.commit()

    return jsonify({"success": True})


# --- Soft delete tag ---
# Purpose: Deactivate a tag without removing the database row.
# Inputs: Tag id path parameter.
# Outputs: JSON success indicator after deactivation.
@tag_manager_bp.route("/api/tags/<int:tag_id>", methods=["DELETE"])
@login_required
@require_permission("tags.manage")
def delete_tag(tag_id):
    tag = Tag.scoped().filter_by(id=tag_id).first_or_404()
    tag.is_active = False
    db.session.commit()

    return jsonify({"success": True})
