"""Base quantity conversion utilities.

Synopsis:
Convert between float quantities and integer base quantities by unit type.

Glossary:
- Base quantity: Integer quantity stored in canonical base units.
- Base scale: Multiplier used to store fractional units precisely.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from app.models import Unit
from sqlalchemy import func
from app.services.unit_conversion import ConversionEngine

DEFAULT_SCALE = 1_000_000
COUNT_SCALE = 32  # Allow 1/32 increments for count-based units

BASE_SCALES = {
    "weight": DEFAULT_SCALE,  # grams
    "volume": DEFAULT_SCALE,  # milliliters
    "length": DEFAULT_SCALE,  # centimeters
    "area": DEFAULT_SCALE,    # square centimeters
    "time": DEFAULT_SCALE,    # seconds
    "count": COUNT_SCALE,     # counts in 1/32
}

DISPLAY_DECIMALS = {
    "weight": 6,
    "volume": 6,
    "length": 6,
    "area": 6,
    "time": 6,
    "count": 5,  # 1/32 = 0.03125
}


# --- Decimal normalize ---
# Purpose: Normalize values into Decimal for accurate scaling.
def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


# --- Resolve unit ---
# Purpose: Resolve a unit record by name or symbol.
def _resolve_unit(unit_name: str | None) -> Optional[Unit]:
    if not unit_name:
        return None
    unit_key = str(unit_name).strip()
    if not unit_key:
        return None
    unit_key_lower = unit_key.lower()
    unit = Unit.query.filter(
        (Unit.name == unit_key) |
        (Unit.symbol == unit_key) |
        (func.lower(Unit.name) == unit_key_lower) |
        (func.lower(Unit.symbol) == unit_key_lower)
    ).first()
    if unit:
        return unit
    try:
        from app.seeders.unit_seeder import seed_units
        seed_units()
    except Exception:
        return None
    return Unit.query.filter(
        (Unit.name == unit_key) |
        (Unit.symbol == unit_key) |
        (func.lower(Unit.name) == unit_key_lower) |
        (func.lower(Unit.symbol) == unit_key_lower)
    ).first()


# --- Base unit name ---
# Purpose: Resolve canonical base unit name from unit metadata.
def _base_unit_name(unit_obj: Optional[Unit], unit_name: str | None) -> str | None:
    if unit_obj:
        return unit_obj.base_unit or unit_obj.name
    return unit_name


# --- Scale lookup ---
# Purpose: Resolve integer scale for a unit type.
def _scale_for_unit_type(unit_type: Optional[str]) -> int:
    if not unit_type:
        return DEFAULT_SCALE
    return BASE_SCALES.get(unit_type, DEFAULT_SCALE)


# --- Display decimals ---
# Purpose: Resolve display precision for a unit type.
def _display_decimals_for_unit_type(unit_type: Optional[str]) -> int:
    if not unit_type:
        return 6
    return DISPLAY_DECIMALS.get(unit_type, 6)


# --- Convert to base unit ---
# Purpose: Convert quantities to canonical base units.
def _convert_to_base_unit_decimal(
    amount: Decimal,
    unit_name: str | None,
    unit_obj: Optional[Unit],
    ingredient_id: Optional[int] = None,
    density: Optional[float] = None,
) -> Tuple[Decimal, Optional[str], Optional[str]]:
    base_unit = _base_unit_name(unit_obj, unit_name)
    unit_type = unit_obj.unit_type if unit_obj else None

    if unit_obj and unit_obj.conversion_factor is not None and base_unit:
        base_amount = amount * _to_decimal(unit_obj.conversion_factor)
        return base_amount, base_unit, unit_type

    if not base_unit:
        return amount, base_unit, unit_type

    result = ConversionEngine.convert_units(
        amount=float(amount),
        from_unit=unit_name,
        to_unit=base_unit,
        ingredient_id=ingredient_id,
        density=density,
        rounding_decimals=None,
    )
    if not result or not result.get("success") or result.get("converted_value") is None:
        raise ValueError(f"Cannot convert {unit_name} to base unit {base_unit}")
    return _to_decimal(result["converted_value"]), base_unit, unit_type


# --- To base quantity ---
# Purpose: Convert a quantity to integer base units.
def to_base_quantity(
    amount: object,
    unit_name: str | None,
    ingredient_id: Optional[int] = None,
    density: Optional[float] = None,
) -> int:
    amount_dec = _to_decimal(amount)
    if amount_dec == 0:
        return 0

    unit_obj = _resolve_unit(unit_name)
    base_amount, _base_unit, unit_type = _convert_to_base_unit_decimal(
        amount_dec, unit_name, unit_obj, ingredient_id=ingredient_id, density=density
    )
    scale = _scale_for_unit_type(unit_type)
    scaled = base_amount * _to_decimal(scale)
    return int(scaled.to_integral_value(rounding=ROUND_HALF_UP))


# --- From base quantity ---
# Purpose: Convert integer base units to display quantity.
def from_base_quantity(
    base_amount: int | None,
    unit_name: str | None,
    ingredient_id: Optional[int] = None,
    density: Optional[float] = None,
    display_decimals: Optional[int] = None,
) -> float:
    if base_amount is None:
        return 0.0

    unit_obj = _resolve_unit(unit_name)
    unit_type = unit_obj.unit_type if unit_obj else None
    base_unit = _base_unit_name(unit_obj, unit_name)
    scale = _scale_for_unit_type(unit_type)
    base_dec = _to_decimal(base_amount) / _to_decimal(scale)

    if unit_obj and unit_obj.conversion_factor and unit_obj.base_unit:
        amount_dec = base_dec / _to_decimal(unit_obj.conversion_factor)
    elif base_unit and unit_name and base_unit != unit_name:
        result = ConversionEngine.convert_units(
            amount=float(base_dec),
            from_unit=base_unit,
            to_unit=unit_name,
            ingredient_id=ingredient_id,
            density=density,
            rounding_decimals=None,
        )
        if not result or not result.get("success") or result.get("converted_value") is None:
            raise ValueError(f"Cannot convert {base_unit} to unit {unit_name}")
        amount_dec = _to_decimal(result["converted_value"])
    else:
        amount_dec = base_dec

    decimals = display_decimals if display_decimals is not None else _display_decimals_for_unit_type(unit_type)
    quantizer = Decimal("1") if decimals <= 0 else Decimal("0." + ("0" * decimals))
    rounded = amount_dec.quantize(quantizer, rounding=ROUND_HALF_UP)
    return float(rounded)


# --- Sync item quantity ---
# Purpose: Update item.quantity from quantity_base.
def sync_item_quantity_from_base(item) -> None:
    item.quantity = from_base_quantity(
        base_amount=getattr(item, "quantity_base", 0),
        unit_name=item.unit,
        ingredient_id=item.id,
        density=item.density,
    )


# --- Sync lot quantities ---
# Purpose: Update lot quantities from base fields.
def sync_lot_quantities_from_base(lot, item=None) -> None:
    ingredient_id = item.id if item else getattr(lot, "inventory_item_id", None)
    density = item.density if item else getattr(lot, "inventory_item", None) and lot.inventory_item.density
    lot.remaining_quantity = from_base_quantity(
        base_amount=getattr(lot, "remaining_quantity_base", 0),
        unit_name=lot.unit,
        ingredient_id=ingredient_id,
        density=density,
    )
    lot.original_quantity = from_base_quantity(
        base_amount=getattr(lot, "original_quantity_base", 0),
        unit_name=lot.unit,
        ingredient_id=ingredient_id,
        density=density,
    )
