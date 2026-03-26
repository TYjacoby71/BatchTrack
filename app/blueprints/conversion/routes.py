import logging

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.services.conversion_route_service import ConversionRouteService
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.utils.permissions import get_effective_organization_id, require_permission

from . import conversion_bp

logger = logging.getLogger(__name__)


def _selected_org_id() -> int | None:
    """Resolve effective organization scope for conversion route actions."""
    return get_effective_organization_id()


@conversion_bp.route("/convert/<float:amount>/<from_unit>/<to_unit>", methods=["GET"])
@require_permission("inventory.view")
def convert(amount, from_unit, to_unit):
    ingredient_id = request.args.get("ingredient_id", type=int)
    density = request.args.get("density", type=float)

    logger.info(
        f"Conversion request: {amount} {from_unit} -> {to_unit}, ingredient_id: {ingredient_id}, density: {density}"
    )

    try:
        result = ConversionEngine.convert_units(
            amount, from_unit, to_unit, ingredient_id=ingredient_id, density=density
        )
        logger.info(f"Conversion result: {result}")
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "converted_value": None,
                    "conversion_type": "error",
                    "error_data": {"message": str(e)},
                    "requires_attention": True,
                }
            ),
            400,
        )


@conversion_bp.route("/units/<int:unit_id>/delete", methods=["POST"])
@require_permission("inventory.edit")
def delete_unit(unit_id):
    unit = ConversionRouteService.get_unit_by_id(unit_id=unit_id)
    if not unit:
        flash("Unit not found", "error")
        return redirect(url_for("conversion_bp.manage_units"))

    if not unit.is_custom:
        flash("Cannot delete system units", "error")
        return redirect(url_for("conversion_bp.manage_units"))

    effective_org_id = _selected_org_id()
    if effective_org_id and unit.organization_id != effective_org_id:
        flash("Cannot delete units from another organization", "error")
        return redirect(url_for("conversion_bp.manage_units"))

    try:
        ConversionRouteService.delete_unit_and_mappings(unit=unit)
        logger.info(f"Successfully deleted unit: {unit.name}")
        flash("Unit deleted successfully", "success")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/conversion/routes.py:67",
            exc_info=True,
        )
        ConversionRouteService.rollback_session()
        flash(f"Error deleting unit: {str(e)}", "error")

    return redirect(url_for("conversion_bp.manage_units"))


@conversion_bp.route("/units", methods=["GET", "POST"])
@require_permission("inventory.edit")
def manage_units():
    from ...utils.unit_utils import get_global_unit_list

    if request.method == "POST":
        try:
            csrf_token = request.form.get("csrf_token")
            validate_csrf(csrf_token)

            # Handle unit creation
            if "unit_name" in request.form:
                name = request.form.get("unit_name").strip()
                symbol = request.form.get("unit_symbol", "").strip() or name
                unit_type = request.form.get("unit_type")

                if not name or not unit_type:
                    flash("Unit name and type are required", "error")
                    return redirect(url_for("conversion_bp.manage_units"))

                # Check for existing unit with same name in the same organization
                existing = ConversionRouteService.find_existing_unit_for_scope(
                    name=name,
                    user_type=getattr(current_user, "user_type", None),
                    user_organization_id=getattr(current_user, "organization_id", None),
                    selected_org_id=_selected_org_id(),
                )

                if existing:
                    if (
                        existing.is_custom
                        and existing.organization_id == current_user.organization_id
                    ):
                        flash(
                            "A custom unit with this name already exists in your organization",
                            "error",
                        )
                    elif not existing.is_custom:
                        flash("A standard unit with this name already exists", "error")
                    else:
                        flash("Unit name not available", "error")
                    return redirect(url_for("conversion_bp.manage_units"))

                ConversionRouteService.create_custom_unit(
                    name=name,
                    symbol=symbol,
                    unit_type=unit_type,
                    created_by=(
                        current_user.id if current_user.is_authenticated else None
                    ),
                    organization_id=(
                        current_user.organization_id
                        if current_user.is_authenticated
                        else None
                    ),
                )
                flash("Unit created successfully", "success")
                return redirect(url_for("conversion_bp.manage_units"))

            # Handle custom unit mapping
            custom_unit = request.form.get("custom_unit", "").strip()
            comparable_unit = request.form.get("comparable_unit", "").strip()
            try:
                conversion_factor = float(request.form.get("conversion_factor", "0"))
            except (TypeError, ValueError):
                flash("Conversion factor must be a number.", "danger")
                return redirect(url_for("conversion_bp.manage_units"))

            if not custom_unit or not comparable_unit or conversion_factor <= 0:
                flash("All fields are required.", "danger")
                return redirect(url_for("conversion_bp.manage_units"))

            custom_unit_obj = ConversionRouteService.find_unit_by_name(name=custom_unit)
            comparable_unit_obj = ConversionRouteService.find_unit_by_name(
                name=comparable_unit
            )

            if not custom_unit_obj or not comparable_unit_obj:
                flash("Units not found in database.", "danger")
                return redirect(url_for("conversion_bp.manage_units"))

            if not custom_unit_obj.is_custom:
                flash("Only custom units can be mapped.", "danger")
                return redirect(url_for("conversion_bp.manage_units"))

            # Allow cross-type mapping only for specific cases
            if custom_unit_obj.unit_type != comparable_unit_obj.unit_type:
                # Allow volume ↔ weight with density
                if {"volume", "weight"} <= {
                    custom_unit_obj.unit_type,
                    comparable_unit_obj.unit_type,
                }:
                    pass  # This is allowed
                # Allow count ↔ volume/weight for custom units (user-defined relationships)
                elif (
                    custom_unit_obj.unit_type == "count"
                    and comparable_unit_obj.unit_type in ["volume", "weight"]
                ):
                    pass  # This is allowed - user knows their apple size
                elif (
                    comparable_unit_obj.unit_type == "count"
                    and custom_unit_obj.unit_type in ["volume", "weight"]
                ):
                    pass  # This is allowed - reverse direction
                else:
                    flash("This type of unit conversion is not supported.", "danger")
                    return redirect(url_for("conversion_bp.manage_units"))

            existing = ConversionRouteService.find_mapping_by_from_unit(
                from_unit=custom_unit
            )
            if existing:
                flash("This custom unit already has a mapping.", "warning")
                return redirect(url_for("conversion_bp.manage_units"))

            # For cross-type mappings (e.g., count to volume/weight), don't calculate base conversion
            # Instead, store the direct relationship in the mapping
            if custom_unit_obj.unit_type != comparable_unit_obj.unit_type:
                # Cross-type mapping - store direct relationship only
                ConversionRouteService.create_cross_type_mapping(
                    custom_unit=custom_unit_obj,
                    comparable_unit=comparable_unit_obj,
                    conversion_factor=conversion_factor,
                    created_by=(
                        current_user.id if current_user.is_authenticated else None
                    ),
                    organization_id=(
                        current_user.organization_id
                        if current_user.is_authenticated
                        else None
                    ),
                )
            else:
                ConversionRouteService.create_same_type_mapping(
                    custom_unit=custom_unit_obj,
                    comparable_unit=comparable_unit_obj,
                    conversion_factor=conversion_factor,
                    created_by=(
                        current_user.id if current_user.is_authenticated else None
                    ),
                    organization_id=(
                        current_user.organization_id
                        if current_user.is_authenticated
                        else None
                    ),
                )
            flash("Custom mapping added successfully.", "success")
            return redirect(url_for("conversion_bp.manage_units"))
        except ValidationError:
            flash("Invalid CSRF token", "danger")
            return redirect(url_for("conversion_bp.manage_units"))

    units = get_global_unit_list()

    # Get mappings scoped by organization
    if current_user and current_user.is_authenticated:
        mappings = ConversionRouteService.list_mappings_for_manage(
            is_authenticated=True,
            user_type=getattr(current_user, "user_type", None),
            user_organization_id=getattr(current_user, "organization_id", None),
            selected_org_id=_selected_org_id(),
        )
    else:
        mappings = []

    units_by_type = {}
    for unit in units:
        if unit.unit_type not in units_by_type:
            units_by_type[unit.unit_type] = []
        units_by_type[unit.unit_type].append(unit)

    return render_template(
        "conversion/units.html",
        units=units,
        units_by_type=units_by_type,
        mappings=mappings,
    )


@conversion_bp.route("/mappings/<int:mapping_id>/delete", methods=["POST"])
@require_permission("inventory.edit")
def delete_mapping(mapping_id):
    mapping = ConversionRouteService.get_mapping_for_delete(
        mapping_id=mapping_id,
        user_type=getattr(current_user, "user_type", None),
        user_organization_id=getattr(current_user, "organization_id", None),
        selected_org_id=_selected_org_id(),
    )
    try:
        ConversionRouteService.delete_mapping(mapping=mapping)
        flash("Mapping deleted successfully.", "success")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/conversion/routes.py:329",
            exc_info=True,
        )
        ConversionRouteService.rollback_session()
        flash(f"Error deleting mapping: {str(e)}", "error")
    return redirect(url_for("conversion_bp.manage_units"))


@conversion_bp.route("/validate_mapping", methods=["POST"])
@require_permission("inventory.edit")
def validate_mapping():
    data = request.get_json()
    from_unit = ConversionRouteService.find_unit_by_name(name=data["from_unit"])
    to_unit = ConversionRouteService.find_unit_by_name(name=data["to_unit"])

    if not from_unit or not to_unit:
        return jsonify({"valid": False, "error": "Units not found"})

    if from_unit.unit_type == to_unit.unit_type:
        return jsonify({"valid": True})

    # Handle volume ↔ weight conversions
    if {"volume", "weight"} <= {from_unit.unit_type, to_unit.unit_type}:
        if data.get("ingredient_id"):
            ingredient = ConversionRouteService.get_inventory_item_by_id(
                item_id=data["ingredient_id"]
            )
            if not ingredient:
                return jsonify({"valid": False, "error": "Ingredient not found"})
            if not ingredient.density and not ingredient.category:
                return jsonify(
                    {
                        "valid": False,
                        "error": "Density required for volume ↔ weight conversion. Set ingredient density first.",
                    }
                )
        else:
            return jsonify(
                {
                    "valid": False,
                    "error": "Volume ↔ weight mappings require ingredient context",
                }
            )

    return jsonify({"valid": True})


@conversion_bp.route("/add_mapping", methods=["POST"])
@require_permission("inventory.edit")
def add_mapping():
    data = request.get_json()

    # Validate units exist
    from_unit = ConversionRouteService.find_unit_by_name(name=data["from_unit"])
    to_unit = ConversionRouteService.find_unit_by_name(name=data["to_unit"])

    if not from_unit or not to_unit:
        return jsonify({"error": "Invalid units"}), 400

    # Cross-type validation
    if from_unit.unit_type != to_unit.unit_type:
        if {"volume", "weight"} <= {from_unit.unit_type, to_unit.unit_type}:
            if not data.get("density"):
                return (
                    jsonify(
                        {"error": "Density required for volume ↔ weight conversion"}
                    ),
                    400,
                )

    ConversionRouteService.create_api_mapping(
        from_unit=data["from_unit"],
        to_unit=data["to_unit"],
        multiplier=float(data["multiplier"]),
        organization_id=(
            current_user.organization_id if current_user.is_authenticated else None
        ),
    )

    return jsonify({"message": "Mapping added successfully"})
