
from ..models import Unit
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

def seed_units():
    from flask import current_app
    from ..models import Unit
    from ..extensions import db
    
    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_units() must be called within Flask application context")
    
    units = [
        # Weight Units
        {"name": "gram", "symbol": "g", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "kg", "symbol": "kg", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 1000.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "mg", "symbol": "mg", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 0.001, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "oz", "symbol": "oz", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 28.3495, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "lb", "symbol": "lb", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 453.592, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "ton", "symbol": "ton", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 907184.74, "is_custom": False, "is_mapped": True, "created_by": None},

        # Volume Units
        {"name": "ml", "symbol": "ml", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "liter", "symbol": "L", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 1000.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "tsp", "symbol": "tsp", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 4.92892, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "tbsp", "symbol": "tbsp", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 14.7868, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "cup", "symbol": "cup", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 236.588, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "pint", "symbol": "pt", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 473.176, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "quart", "symbol": "qt", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 946.353, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "gallon", "symbol": "gal", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 3785.41, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "floz", "symbol": "fl oz", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 29.5735, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "drop", "symbol": "drop", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 0.05, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "dram", "symbol": "dram", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 3.69669, "is_custom": False, "is_mapped": True, "created_by": None},

        # Length Units
        {"name": "cm", "symbol": "cm", "unit_type": "length", "base_unit": "cm", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "mm", "symbol": "mm", "unit_type": "length", "base_unit": "cm", "conversion_factor": 0.1, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "inch", "symbol": "in", "unit_type": "length", "base_unit": "cm", "conversion_factor": 2.54, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "ft", "symbol": "ft", "unit_type": "length", "base_unit": "cm", "conversion_factor": 30.48, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "yard", "symbol": "yd", "unit_type": "length", "base_unit": "cm", "conversion_factor": 91.44, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "meter", "symbol": "m", "unit_type": "length", "base_unit": "cm", "conversion_factor": 100.0, "is_custom": False, "is_mapped": True, "created_by": None},

        # Area Units
        {"name": "sqcm", "symbol": "cm²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "sqm", "symbol": "m²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 10000.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "sqinch", "symbol": "in²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 6.4516, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "sqft", "symbol": "ft²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 929.03, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "sqyard", "symbol": "yd²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 8361.27, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "acre", "symbol": "acre", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 40468564.0, "is_custom": False, "is_mapped": True, "created_by": None},

        # Cubic Volume Units
        {"name": "cubicinch", "symbol": "in³", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 16.3871, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "cubicfoot", "symbol": "ft³", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 28316.8, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "cubicyard", "symbol": "yd³", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 764555.0, "is_custom": False, "is_mapped": True, "created_by": None},

        # Count Units
        {"name": "count", "symbol": "ct", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "pack", "symbol": "pk", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "dozen", "symbol": "dz", "unit_type": "count", "base_unit": "count", "conversion_factor": 12.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "unit", "symbol": "unit", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "batch", "symbol": "batch", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "pair", "symbol": "pair", "unit_type": "count", "base_unit": "count", "conversion_factor": 2.0, "is_custom": False, "is_mapped": True, "created_by": None},

        # Time Units
        {"name": "second", "symbol": "s", "unit_type": "time", "base_unit": "second", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "minute", "symbol": "min", "unit_type": "time", "base_unit": "second", "conversion_factor": 60.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "hour", "symbol": "hr", "unit_type": "time", "base_unit": "second", "conversion_factor": 3600.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "day", "symbol": "day", "unit_type": "time", "base_unit": "second", "conversion_factor": 86400.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "week", "symbol": "wk", "unit_type": "time", "base_unit": "second", "conversion_factor": 604800.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "month", "symbol": "mo", "unit_type": "time", "base_unit": "second", "conversion_factor": 2592000.0, "is_custom": False, "is_mapped": True, "created_by": None},
        {"name": "year", "symbol": "yr", "unit_type": "time", "base_unit": "second", "conversion_factor": 31536000.0, "is_custom": False, "is_mapped": True, "created_by": None},
    ]

    print(f"=== Seeding {len(units)} standard units ===")
    
    # Seed regular units
    added_count = 0
    for unit_data in units:
        if not Unit.query.filter_by(name=unit_data["name"]).first():
            unit = Unit(**unit_data)
            db.session.add(unit)
            added_count += 1
            
    try:
        db.session.commit()
        print(f"✅ Added {added_count} new units")
        print(f"ℹ️  Total units in database: {Unit.query.count()}")
    except Exception as e:
        print(f"❌ Error seeding units: {e}")
        db.session.rollback()
        raise
