"""
Conversion Service Drawer Error Handler

Owns all decisions about when conversion errors require drawers and what type.
This is the single source of truth for conversion error UX decisions.
"""

import uuid


def handle_conversion_error(conversion_result):
    """
    Convert a ConversionEngine error result into a standardized drawer response.

    This is the ONLY place where conversion error -> drawer decisions are made.
    Any service that uses ConversionEngine should call this function.
    """
    if conversion_result.get("success"):
        return {"requires_drawer": False}

    error_code = conversion_result.get("error_code")
    error_data = conversion_result.get("error_data", {})

    if error_code == "MISSING_DENSITY":
        ingredient_id = error_data.get("ingredient_id")
        correlation_id = str(uuid.uuid4())
        return {
            "requires_drawer": True,
            "drawer_type": "conversion.density_fix",
            "drawer_action": "open_density_modal",
            "drawer_data": {
                "ingredient_id": ingredient_id,
                "ingredient_name": error_data.get("ingredient_name"),
                "from_unit": error_data.get("from_unit"),
                "to_unit": error_data.get("to_unit"),
                "api_endpoint": f"/api/drawers/conversion/density-modal/{ingredient_id}",
                "help_link": "/conversion/units",
            },
            "drawer_payload": {
                "version": "1.0",
                "modal_url": f"/api/drawers/conversion/density-modal/{ingredient_id}",
                "success_event": "conversion.density.updated",
                "error_type": "conversion",
                "error_code": "MISSING_DENSITY",
                "error_message": "Missing density for conversion",
                "correlation_id": correlation_id,
            },
            "suggested_density": _get_suggested_density(
                error_data.get("ingredient_name", "")
            ),
            "error_message": "Missing density for conversion",
        }

    elif error_code == "MISSING_CUSTOM_MAPPING":
        from_unit = error_data.get("from_unit")
        to_unit = error_data.get("to_unit")
        correlation_id = str(uuid.uuid4())
        return {
            "requires_drawer": True,
            "drawer_type": "conversion.unit_mapping_fix",
            "drawer_action": "open_unit_mapping_modal",
            "drawer_data": {
                "from_unit": from_unit,
                "to_unit": to_unit,
                "api_endpoint": f"/api/drawers/conversion/unit-mapping-modal?from_unit={from_unit}&to_unit={to_unit}",
                "unit_manager_link": "/conversion/units",
            },
            "drawer_payload": {
                "version": "1.0",
                "modal_url": f"/api/drawers/conversion/unit-mapping-modal?from_unit={from_unit}&to_unit={to_unit}",
                "success_event": "conversion.unit_mapping.created",
                "error_type": "conversion",
                "error_code": "MISSING_CUSTOM_MAPPING",
                "error_message": "Missing custom unit mapping",
                "correlation_id": correlation_id,
            },
            "error_message": "Missing custom unit mapping",
        }

    elif error_code in ["UNKNOWN_SOURCE_UNIT", "UNKNOWN_TARGET_UNIT"]:
        unknown_unit = error_data.get("unit")
        correlation_id = str(uuid.uuid4())
        return {
            "requires_drawer": True,
            "drawer_type": "conversion.unit_creation",
            "drawer_action": "redirect_unit_manager",
            "drawer_data": {
                "unknown_unit": unknown_unit,
                "unit_manager_link": "/conversion/units",
            },
            "drawer_payload": {
                "version": "1.0",
                "redirect_url": "/conversion/units",
                "error_type": "conversion",
                "error_code": error_code,
                "error_message": f"Unknown unit requires manual setup: {unknown_unit}",
                "correlation_id": correlation_id,
            },
            "error_message": f"Unknown unit: {unknown_unit}",
        }

    elif error_code == "SYSTEM_ERROR":
        return {
            "requires_drawer": False,
            "error_type": "system_error",
            "error_message": "Unit conversion is not available at the moment, please try again",
        }

    else:
        # For all other conversion errors, don't show a drawer
        return {
            "requires_drawer": False,
            "error_type": "conversion_error",
            "error_message": error_data.get("message", "Conversion failed"),
        }


def generate_drawer_payload_for_conversion_error(
    error_code, error_data, retry_operation=None, retry_data=None
):
    """
    Generate drawer payload for conversion errors that require UI intervention.
    This is called by services that need to handle conversion errors with drawers.
    """
    correlation_id = str(uuid.uuid4())
    if error_code == "MISSING_DENSITY":
        ingredient_id = error_data.get("ingredient_id")
        payload = {
            "version": "1.0",
            "modal_url": f"/api/drawers/conversion/density-modal/{ingredient_id}",
            "success_event": "conversion.density.updated",
            "error_type": "conversion",
            "error_code": error_code,
            "error_message": error_data.get(
                "message", "Missing density for conversion"
            ),
            "correlation_id": correlation_id,
        }
    elif error_code == "MISSING_CUSTOM_MAPPING":
        from_unit = error_data.get("from_unit")
        to_unit = error_data.get("to_unit")
        payload = {
            "version": "1.0",
            "modal_url": f"/api/drawers/conversion/unit-mapping-modal?from_unit={from_unit}&to_unit={to_unit}",
            "success_event": "conversion.unit_mapping.created",
            "error_type": "conversion",
            "error_code": error_code,
            "error_message": error_data.get("message", "Missing custom unit mapping"),
            "correlation_id": correlation_id,
        }
    elif error_code in ["UNKNOWN_SOURCE_UNIT", "UNKNOWN_TARGET_UNIT"]:
        payload = {
            "version": "1.0",
            "redirect_url": "/conversion/units",
            "error_type": "conversion",
            "error_code": error_code,
            "error_message": error_data.get(
                "message", "Unknown unit requires manual setup"
            ),
            "correlation_id": correlation_id,
        }
    else:
        return None

    # Add retry information if provided
    if retry_operation and retry_data:
        payload["retry"] = {
            "mode": "frontend_callback",
            "operation": retry_operation,
            "data": retry_data,
        }

    return payload


def _get_suggested_density(ingredient_name):
    """Get suggested density for common ingredients"""
    if not ingredient_name:
        return None

    density_suggestions = {
        "beeswax": 0.96,
        "wax": 0.93,
        "honey": 1.42,
        "oil": 0.91,
        "water": 1.0,
        "milk": 1.03,
        "butter": 0.92,
        "cream": 0.994,
        "syrup": 1.37,
    }

    ingredient_lower = ingredient_name.lower()
    for key, density in density_suggestions.items():
        if key in ingredient_lower:
            return density
    return None


def prepare_density_error_context(ingredient, error_data=None):
    """Prepare context for density error modal"""
    suggested_density = None
    if ingredient.category and ingredient.category.default_density:
        suggested_density = ingredient.category.default_density
    else:
        suggested_density = _get_suggested_density(ingredient.name)

    return {
        "ingredient": ingredient,
        "suggested_density": suggested_density,
        "current_density": ingredient.density,
        "error_data": error_data or {},
    }


def prepare_unit_mapping_error_context(from_unit, to_unit, error_data=None):
    """Prepare context for unit mapping error modal"""
    return {"from_unit": from_unit, "to_unit": to_unit, "error_data": error_data or {}}
