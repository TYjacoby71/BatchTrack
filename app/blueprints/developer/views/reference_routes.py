from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from sqlalchemy import func

from app.extensions import db
from app.models import GlobalItem
from app.models.ingredient_reference import PhysicalForm
from app.services.developer.reference_data_service import ReferenceDataService
from app.utils.seo import slugify_value

from ..routes import developer_bp


def _generate_unique_slug(model, seed: str) -> str:
    base_slug = slugify_value(seed or "item")
    candidate = base_slug
    counter = 2
    while model.query.filter_by(slug=candidate).first():
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


@developer_bp.route("/reference-categories")
@login_required
def reference_categories():
    """Manage global ingredient categories."""
    from app.models.category import IngredientCategory

    existing_categories = (
        IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True,
        )
        .order_by(IngredientCategory.name)
        .all()
    )

    categories = [cat.name for cat in existing_categories]
    global_items_by_category = {}
    category_densities = {}

    for category_obj in existing_categories:
        items = GlobalItem.query.filter_by(
            ingredient_category_id=category_obj.id, is_archived=False
        ).all()
        global_items_by_category[category_obj.name] = items
        if category_obj.default_density:
            category_densities[category_obj.name] = category_obj.default_density

    return render_template(
        "developer/reference_categories.html",
        categories=categories,
        global_items_by_category=global_items_by_category,
        category_densities=category_densities,
    )


@developer_bp.route("/reference-categories/add", methods=["POST"])
@login_required
def add_reference_category():
    """Add a new global ingredient category."""
    try:
        data = request.get_json() or {}
        category_name = data.get("name", "").strip()
        default_density = data.get("default_density")

        if not category_name:
            return jsonify({"success": False, "error": "Category name is required"})

        from app.models.category import IngredientCategory

        existing = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
        ).first()

        if existing:
            return jsonify({"success": False, "error": "Category already exists"})

        new_category = IngredientCategory(
            name=category_name,
            is_global_category=True,
            organization_id=None,
            is_active=True,
            default_density=default_density if isinstance(default_density, (int, float)) else None,
        )

        db.session.add(new_category)
        db.session.commit()

        return jsonify({"success": True, "message": f'Category "{category_name}" added successfully'})

    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)})


@developer_bp.route("/reference-categories/delete", methods=["POST"])
@login_required
def delete_reference_category():
    """Delete a global ingredient category."""
    try:
        data = request.get_json() or {}
        category_name = data.get("name", "").strip()

        if not category_name:
            return jsonify({"success": False, "error": "Category name is required"})

        from app.models.category import IngredientCategory

        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
        ).first()

        if not category:
            return jsonify({"success": False, "error": "Category not found"})

        linked_items = GlobalItem.query.filter_by(ingredient_category_id=category.id).count()
        if linked_items:
            return jsonify(
                {
                    "success": False,
                    "error": f"Category is linked to {linked_items} global items. Reassign before deleting.",
                }
            )

        db.session.delete(category)
        db.session.commit()

        return jsonify({"success": True, "message": f'Category "{category_name}" deleted successfully'})

    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)})


@developer_bp.route("/reference-categories/update-density", methods=["POST"])
@login_required
def update_reference_category_density():
    """Update default density for category and linked items."""
    try:
        data = request.get_json() or {}
        category_name = data.get("name", "").strip()
        density = data.get("default_density")

        if not category_name:
            return jsonify({"success": False, "error": "Category name is required"})

        if density in (None, ""):
            return jsonify({"success": False, "error": "Density value is required"})

        try:
            density_value = float(density)
        except ValueError:
            return jsonify({"success": False, "error": "Density must be a numeric value"})

        from app.models.category import IngredientCategory

        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
        ).first()

        if not category:
            return jsonify({"success": False, "error": "Category not found"})

        category.default_density = density_value
        GlobalItem.query.filter_by(ingredient_category_id=category.id).update(
            {GlobalItem.density: density_value}
        )

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f'Category "{category_name}" density set to {density_value}',
            }
        )

    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)})


@developer_bp.route("/reference-categories/calculate-density", methods=["POST"])
@login_required
def calculate_category_density():
    """Calculate average density for category."""
    try:
        data = request.get_json() or {}
        category_name = data.get("name", "").strip()

        if not category_name:
            return jsonify({"success": False, "error": "Category name is required"})

        from app.models.category import IngredientCategory

        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
        ).first()

        if not category:
            return jsonify({"success": False, "error": "Category not found"})

        densities = [
            item.density
            for item in GlobalItem.query.filter_by(ingredient_category_id=category.id)
            .filter(GlobalItem.density.isnot(None))
            .all()
            if item.density
        ]

        if not densities:
            return jsonify({"success": False, "error": "No items with valid density values found"})

        calculated_density = sum(densities) / len(densities)

        return jsonify(
            {
                "success": True,
                "calculated_density": calculated_density,
                "items_count": len(densities),
                "message": f"Calculated density: {calculated_density:.3f} g/ml from {len(densities)} items",
            }
        )

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)})


@developer_bp.route("/container-management")
@login_required
def container_management():
    """Container management page for curating materials, colors, styles."""
    curated_lists = ReferenceDataService.load_curated_container_lists()
    return render_template(
        "developer/container_management.html",
        curated_materials=curated_lists["materials"],
        curated_types=curated_lists["types"],
        curated_styles=curated_lists["styles"],
        curated_colors=curated_lists["colors"],
    )


@developer_bp.route("/container-management/save-curated", methods=["POST"])
@login_required
def save_curated_container_lists():
    """Save curated container lists to settings.json."""
    try:
        data = request.get_json() or {}
        curated_lists = data.get("curated_lists", {})

        required_keys = ["materials", "types", "styles", "colors"]
        for key in required_keys:
            if key not in curated_lists or not isinstance(curated_lists[key], list):
                return jsonify({"success": False, "error": f"Invalid or missing {key} list"})

        ReferenceDataService.save_curated_container_lists(curated_lists)
        return jsonify({"success": True, "message": "Curated lists saved successfully"})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)})


@developer_bp.route("/api/container-options")
@login_required
def api_container_options():
    """Get curated container options for dropdowns."""
    try:
        curated_lists = ReferenceDataService.load_curated_container_lists()
        return jsonify({"success": True, "options": curated_lists})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)})


@developer_bp.route("/physical-forms", methods=["GET"])
@login_required
def manage_physical_forms():
    """Curate physical forms used by global items."""
    forms = PhysicalForm.query.order_by(PhysicalForm.name.asc()).all()
    usage_rows = (
        db.session.query(GlobalItem.physical_form_id, func.count(GlobalItem.id))
        .filter(
            GlobalItem.physical_form_id.isnot(None),
            GlobalItem.is_archived != True,
        )
        .group_by(GlobalItem.physical_form_id)
        .all()
    )
    usage_map = {form_id: count for form_id, count in usage_rows}
    return render_template(
        "developer/physical_forms.html",
        forms=forms,
        usage_map=usage_map,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Physical Forms"},
        ],
    )


@developer_bp.route("/physical-forms", methods=["POST"])
@login_required
def create_physical_form():
    """Create a new physical form entry."""
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        flash("Physical form name is required.", "error")
        return redirect(url_for("developer.manage_physical_forms"))

    existing = (
        PhysicalForm.query.filter(func.lower(PhysicalForm.name) == func.lower(name))
        .order_by(PhysicalForm.id.asc())
        .first()
    )
    if existing:
        flash(f'Physical form "{name}" already exists.', "error")
        return redirect(url_for("developer.manage_physical_forms"))

    slug = _generate_unique_slug(PhysicalForm, name)
    new_form = PhysicalForm(name=name, slug=slug, description=description, is_active=True)
    db.session.add(new_form)
    db.session.commit()
    flash(f'Physical form "{name}" created.', "success")
    return redirect(url_for("developer.manage_physical_forms"))


@developer_bp.route("/physical-forms/<int:form_id>/toggle", methods=["POST"])
@login_required
def toggle_physical_form(form_id: int):
    """Toggle a physical form's active state."""
    physical_form = PhysicalForm.query.get_or_404(form_id)
    physical_form.is_active = not physical_form.is_active
    db.session.commit()
    state = "activated" if physical_form.is_active else "archived"
    flash(f'Physical form "{physical_form.name}" {state}.', "success")
    return redirect(url_for("developer.manage_physical_forms"))
