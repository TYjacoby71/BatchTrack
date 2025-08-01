
from datetime import datetime
from ..models import Unit
from ..extensions import db

def seed_units():
    from flask import current_app
    from ..models import Unit
    from ..extensions import db
    
    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_units() must be called within Flask application context")
    
    units = [
        # Weight Units
        {"name": "gram", "symbol": "g", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "kg", "symbol": "kg", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 1000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "mg", "symbol": "mg", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 0.001, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "oz", "symbol": "oz", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 28.3495, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "lb", "symbol": "lb", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 453.592, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "ton", "symbol": "ton", "unit_type": "weight", "base_unit": "gram", "conversion_factor": 907184.74, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Volume Units
        {"name": "ml", "symbol": "ml", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "liter", "symbol": "L", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 1000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "tsp", "symbol": "tsp", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 4.92892, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "tbsp", "symbol": "tbsp", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 14.7868, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "cup", "symbol": "cup", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 236.588, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "pint", "symbol": "pt", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 473.176, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "quart", "symbol": "qt", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 946.353, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "gallon", "symbol": "gal", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 3785.41, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "floz", "symbol": "fl oz", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 29.5735, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "drop", "symbol": "drop", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 0.05, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "dram", "symbol": "dram", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 3.69669, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Length Units
        {"name": "cm", "symbol": "cm", "unit_type": "length", "base_unit": "cm", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "mm", "symbol": "mm", "unit_type": "length", "base_unit": "cm", "conversion_factor": 0.1, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "inch", "symbol": "in", "unit_type": "length", "base_unit": "cm", "conversion_factor": 2.54, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "ft", "symbol": "ft", "unit_type": "length", "base_unit": "cm", "conversion_factor": 30.48, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "yard", "symbol": "yd", "unit_type": "length", "base_unit": "cm", "conversion_factor": 91.44, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "meter", "symbol": "m", "unit_type": "length", "base_unit": "cm", "conversion_factor": 100.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Area Units
        {"name": "sqcm", "symbol": "cm²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqm", "symbol": "m²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 10000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqinch", "symbol": "in²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 6.4516, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqft", "symbol": "ft²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 929.03, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqyard", "symbol": "yd²", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 8361.27, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "acre", "symbol": "acre", "unit_type": "area", "base_unit": "sqcm", "conversion_factor": 40468564.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Cubic Volume Units
        {"name": "cubicinch", "symbol": "in³", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 16.3871, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "cubicfoot", "symbol": "ft³", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 28316.8, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "cubicyard", "symbol": "yd³", "unit_type": "volume", "base_unit": "ml", "conversion_factor": 764555.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Count Units
        {"name": "count", "symbol": "ct", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "pack", "symbol": "pk", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "dozen", "symbol": "dz", "unit_type": "count", "base_unit": "count", "conversion_factor": 12.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "unit", "symbol": "unit", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "batch", "symbol": "batch", "unit_type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "pair", "symbol": "pair", "unit_type": "count", "base_unit": "count", "conversion_factor": 2.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Time Units
        {"name": "second", "symbol": "s", "unit_type": "time", "base_unit": "second", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "minute", "symbol": "min", "unit_type": "time", "base_unit": "second", "conversion_factor": 60.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "hour", "symbol": "hr", "unit_type": "time", "base_unit": "second", "conversion_factor": 3600.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "day", "symbol": "day", "unit_type": "time", "base_unit": "second", "conversion_factor": 86400.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "week", "symbol": "wk", "unit_type": "time", "base_unit": "second", "conversion_factor": 604800.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "month", "symbol": "mo", "unit_type": "time", "base_unit": "second", "conversion_factor": 2592000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "year", "symbol": "yr", "unit_type": "time", "base_unit": "second", "conversion_factor": 31536000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
    ]

    # Seed regular units
    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))

    db.session.commit()
