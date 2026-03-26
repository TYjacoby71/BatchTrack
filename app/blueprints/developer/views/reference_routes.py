"""Module documentation.

Synopsis:
This module defines route handlers and helpers for `app/blueprints/developer/views/reference_routes.py`.

Glossary:
- Route handler: A Flask view function bound to an endpoint.
- Helper unit: A module-level function or class supporting route/service flow.
"""

from __future__ import annotations

import logging

from flask import flash, jsonify, redirect, render_template, request, url_for
from app.services.developer.reference_data_service import ReferenceDataService
from app.services.developer.reference_route_service import ReferenceRouteService

from ..decorators import require_developer_permission
from ..routes import developer_bp

logger = logging.getLogger(__name__)

# --- Reference Categories ---
# Purpose: Define the top-level behavior of `reference_categories` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/reference-categories")
@require_developer_permission("dev.system_admin")
def reference_categories():
    """Manage global ingredient categories."""
    context = ReferenceRouteService.get_reference_categories_context()
    return render_template(
        "developer/reference_categories.html",
        categories=context["categories"],
        global_items_by_category=context["global_items_by_category"],
        category_densities=context["category_densities"],
    )


# --- Add Reference Category ---
# Purpose: Define the top-level behavior of `add_reference_category` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/reference-categories/add", methods=["POST"])
@require_developer_permission("dev.system_admin")
def add_reference_category():
    """Add a new global ingredient category."""
    return jsonify(ReferenceRouteService.add_reference_category(request.get_json() or {}))


# --- Delete Reference Category ---
# Purpose: Define the top-level behavior of `delete_reference_category` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/reference-categories/delete", methods=["POST"])
@require_developer_permission("dev.system_admin")
def delete_reference_category():
    """Delete a global ingredient category."""
    return jsonify(
        ReferenceRouteService.delete_reference_category(request.get_json() or {})
    )


# --- Update Reference Category Density ---
# Purpose: Define the top-level behavior of `update_reference_category_density` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/reference-categories/update-density", methods=["POST"])
@require_developer_permission("dev.system_admin")
def update_reference_category_density():
    """Update default density for category and linked items."""
    return jsonify(
        ReferenceRouteService.update_reference_category_density(request.get_json() or {})
    )


# --- Calculate Category Density ---
# Purpose: Define the top-level behavior of `calculate_category_density` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/reference-categories/calculate-density", methods=["POST"])
@require_developer_permission("dev.system_admin")
def calculate_category_density():
    """Calculate average density for category."""
    return jsonify(ReferenceRouteService.calculate_category_density(request.get_json() or {}))


# --- Container Management ---
# Purpose: Define the top-level behavior of `container_management` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/container-management")
@require_developer_permission("dev.system_admin")
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


# --- Save Curated Container Lists ---
# Purpose: Define the top-level behavior of `save_curated_container_lists` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/container-management/save-curated", methods=["POST"])
@require_developer_permission("dev.system_admin")
def save_curated_container_lists():
    """Save curated container lists to app settings."""
    try:
        data = request.get_json() or {}
        curated_lists = data.get("curated_lists", {})

        required_keys = ["materials", "types", "styles", "colors"]
        for key in required_keys:
            if key not in curated_lists or not isinstance(curated_lists[key], list):
                return jsonify(
                    {"success": False, "error": f"Invalid or missing {key} list"}
                )

        ReferenceDataService.save_curated_container_lists(curated_lists)
        return jsonify({"success": True, "message": "Curated lists saved successfully"})
    except Exception as exc:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/developer/views/reference_routes.py:335",
            exc_info=True,
        )
        return jsonify({"success": False, "error": str(exc)})


# --- Api Container Options ---
# Purpose: Define the top-level behavior of `api_container_options` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/api/container-options")
@require_developer_permission("dev.system_admin")
def api_container_options():
    """Get curated container options for dropdowns."""
    try:
        curated_lists = ReferenceDataService.load_curated_container_lists()
        return jsonify({"success": True, "options": curated_lists})
    except Exception as exc:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/developer/views/reference_routes.py:350",
            exc_info=True,
        )
        return jsonify({"success": False, "error": str(exc)})


# --- Manage Ingredient Attributes ---
# Purpose: Define the top-level behavior of `manage_ingredient_attributes` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/ingredient-attributes", methods=["GET"])
@require_developer_permission("dev.system_admin")
def manage_ingredient_attributes():
    """Curate ingredient lookup tables: tags, physical forms, variations."""
    context = ReferenceRouteService.get_ingredient_attributes_context()
    return render_template(
        "developer/ingredient_attributes.html",
        physical_forms=context["physical_forms"],
        variations=context["variations"],
        variation_usage=context["variation_usage"],
        function_tags=context["function_tags"],
        application_tags=context["application_tags"],
        category_tags=context["category_tags"],
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Ingredient Attributes"},
        ],
    )


# --- Legacy Physical Forms Redirect ---
# Purpose: Define the top-level behavior of `legacy_physical_forms_redirect` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/physical-forms", methods=["GET"])
@require_developer_permission("dev.system_admin")
def legacy_physical_forms_redirect():
    """Backwards-compatible redirect to the new ingredient attributes hub."""
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Create Physical Form ---
# Purpose: Define the top-level behavior of `create_physical_form` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/ingredient-attributes/physical-forms", methods=["POST"])
@require_developer_permission("dev.system_admin")
def create_physical_form():
    """Create a new physical form entry."""
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        flash("Physical form name is required.", "error")
        return redirect(url_for("developer.manage_ingredient_attributes"))
    success, message = ReferenceRouteService.create_physical_form(name, description)
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Toggle Physical Form ---
# Purpose: Define the top-level behavior of `toggle_physical_form` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route(
    "/ingredient-attributes/physical-forms/<int:form_id>/toggle", methods=["POST"]
)
@require_developer_permission("dev.system_admin")
def toggle_physical_form(form_id: int):
    """Toggle a physical form's active state."""
    physical_form = ReferenceRouteService.toggle_physical_form(form_id)
    state = "activated" if physical_form.is_active else "archived"
    flash(f'Physical form "{physical_form.name}" {state}.', "success")
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Create Variation ---
# Purpose: Define the top-level behavior of `create_variation` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/ingredient-attributes/variations", methods=["POST"])
@require_developer_permission("dev.system_admin")
def create_variation():
    """Create a curated variation entry."""
    name = (request.form.get("name") or "").strip()
    physical_form_id = (request.form.get("physical_form_id") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    default_unit = (request.form.get("default_unit") or "").strip() or None
    form_bypass = request.form.get("form_bypass") == "on"

    if not name:
        flash("Variation name is required.", "error")
        return redirect(url_for("developer.manage_ingredient_attributes"))

    success, message = ReferenceRouteService.create_variation(
        name=name,
        physical_form_id=physical_form_id,
        description=description,
        default_unit=default_unit,
        form_bypass=form_bypass,
    )
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Toggle Variation ---
# Purpose: Define the top-level behavior of `toggle_variation` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route(
    "/ingredient-attributes/variations/<int:variation_id>/toggle", methods=["POST"]
)
@require_developer_permission("dev.system_admin")
def toggle_variation(variation_id: int):
    variation = ReferenceRouteService.toggle_variation(variation_id)
    state = "activated" if variation.is_active else "archived"
    flash(f'Variation "{variation.name}" {state}.', "success")
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Create Function Tag ---
# Purpose: Define the top-level behavior of `create_function_tag` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/ingredient-attributes/function-tags", methods=["POST"])
@require_developer_permission("dev.system_admin")
def create_function_tag():
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        flash("Function tag name is required.", "error")
        return redirect(url_for("developer.manage_ingredient_attributes"))
    ReferenceRouteService.save_function_tag(name, description)
    flash(f'Function tag "{name}" saved.', "success")
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Create Application Tag ---
# Purpose: Define the top-level behavior of `create_application_tag` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/ingredient-attributes/application-tags", methods=["POST"])
@require_developer_permission("dev.system_admin")
def create_application_tag():
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        flash("Application tag name is required.", "error")
        return redirect(url_for("developer.manage_ingredient_attributes"))
    ReferenceRouteService.save_application_tag(name, description)
    flash(f'Application tag "{name}" saved.', "success")
    return redirect(url_for("developer.manage_ingredient_attributes"))


# --- Create Category Tag ---
# Purpose: Define the top-level behavior of `create_category_tag` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/ingredient-attributes/category-tags", methods=["POST"])
@require_developer_permission("dev.system_admin")
def create_category_tag():
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        flash("Category tag name is required.", "error")
        return redirect(url_for("developer.manage_ingredient_attributes"))
    ReferenceRouteService.save_category_tag(name, description)
    flash(f'Use case tag "{name}" saved.', "success")
    return redirect(url_for("developer.manage_ingredient_attributes"))
