
"""
Unit Conversion Service Package

Provides unit conversion capabilities and owns all conversion error handling decisions.
"""

from .unit_conversion import ConversionEngine
from . import drawer_errors

class UnitConversionService:
    """Compatibility wrapper for legacy unit conversion calls."""

    @staticmethod
    def convert_with_density(from_amount, from_unit, to_unit, density=None):
        result = ConversionEngine.convert_units(
            amount=from_amount,
            from_unit=from_unit,
            to_unit=to_unit,
            density=density,
        )

        if result.get("success"):
            return {
                "success": True,
                "converted_amount": result.get("converted_value"),
                "conversion_type": result.get("conversion_type"),
            }

        error_message = None
        error_data = result.get("error_data")
        if isinstance(error_data, dict):
            error_message = error_data.get("message")
        return {
            "success": False,
            "error": error_message or result.get("error_code") or "Conversion failed",
        }


__all__ = ["ConversionEngine", "UnitConversionService", "drawer_errors"]
