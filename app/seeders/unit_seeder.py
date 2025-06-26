
from datetime import datetime
from ..models import Unit
from ..extensions import db

def seed_units():
    units = [
        # Weight Units
        {"name": "gram", "symbol": "g", "type": "weight", "base_unit": "gram", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "kg", "symbol": "kg", "type": "weight", "base_unit": "gram", "conversion_factor": 1000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "mg", "symbol": "mg", "type": "weight", "base_unit": "gram", "conversion_factor": 0.001, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "oz", "symbol": "oz", "type": "weight", "base_unit": "gram", "conversion_factor": 28.3495, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "lb", "symbol": "lb", "type": "weight", "base_unit": "gram", "conversion_factor": 453.592, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "ton", "symbol": "ton", "type": "weight", "base_unit": "gram", "conversion_factor": 907184.74, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Volume Units
        {"name": "ml", "symbol": "ml", "type": "volume", "base_unit": "ml", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "liter", "symbol": "L", "type": "volume", "base_unit": "ml", "conversion_factor": 1000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "tsp", "symbol": "tsp", "type": "volume", "base_unit": "ml", "conversion_factor": 4.92892, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "tbsp", "symbol": "tbsp", "type": "volume", "base_unit": "ml", "conversion_factor": 14.7868, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "cup", "symbol": "cup", "type": "volume", "base_unit": "ml", "conversion_factor": 236.588, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "pint", "symbol": "pt", "type": "volume", "base_unit": "ml", "conversion_factor": 473.176, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "quart", "symbol": "qt", "type": "volume", "base_unit": "ml", "conversion_factor": 946.353, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "gallon", "symbol": "gal", "type": "volume", "base_unit": "ml", "conversion_factor": 3785.41, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "floz", "symbol": "fl oz", "type": "volume", "base_unit": "ml", "conversion_factor": 29.5735, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "drop", "symbol": "drop", "type": "volume", "base_unit": "ml", "conversion_factor": 0.05, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "dram", "symbol": "dram", "type": "volume", "base_unit": "ml", "conversion_factor": 3.69669, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Length Units
        {"name": "cm", "symbol": "cm", "type": "length", "base_unit": "cm", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "mm", "symbol": "mm", "type": "length", "base_unit": "cm", "conversion_factor": 0.1, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "inch", "symbol": "in", "type": "length", "base_unit": "cm", "conversion_factor": 2.54, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "ft", "symbol": "ft", "type": "length", "base_unit": "cm", "conversion_factor": 30.48, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "yard", "symbol": "yd", "type": "length", "base_unit": "cm", "conversion_factor": 91.44, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "meter", "symbol": "m", "type": "length", "base_unit": "cm", "conversion_factor": 100.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Area Units
        {"name": "sqcm", "symbol": "cm²", "type": "area", "base_unit": "sqcm", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqm", "symbol": "m²", "type": "area", "base_unit": "sqcm", "conversion_factor": 10000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqinch", "symbol": "in²", "type": "area", "base_unit": "sqcm", "conversion_factor": 6.4516, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqft", "symbol": "ft²", "type": "area", "base_unit": "sqcm", "conversion_factor": 929.03, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "sqyard", "symbol": "yd²", "type": "area", "base_unit": "sqcm", "conversion_factor": 8361.27, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "acre", "symbol": "acre", "type": "area", "base_unit": "sqcm", "conversion_factor": 40468564.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Cubic Volume Units
        {"name": "cubicinch", "symbol": "in³", "type": "volume", "base_unit": "ml", "conversion_factor": 16.3871, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "cubicfoot", "symbol": "ft³", "type": "volume", "base_unit": "ml", "conversion_factor": 28316.8, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "cubicyard", "symbol": "yd³", "type": "volume", "base_unit": "ml", "conversion_factor": 764555.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Count Units
        {"name": "count", "symbol": "ct", "type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "pack", "symbol": "pk", "type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "dozen", "symbol": "dz", "type": "count", "base_unit": "count", "conversion_factor": 12.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "unit", "symbol": "unit", "type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "batch", "symbol": "batch", "type": "count", "base_unit": "count", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "pair", "symbol": "pair", "type": "count", "base_unit": "count", "conversion_factor": 2.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},

        # Time Units
        {"name": "second", "symbol": "s", "type": "time", "base_unit": "second", "conversion_factor": 1.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "minute", "symbol": "min", "type": "time", "base_unit": "second", "conversion_factor": 60.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "hour", "symbol": "hr", "type": "time", "base_unit": "second", "conversion_factor": 3600.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "day", "symbol": "day", "type": "time", "base_unit": "second", "conversion_factor": 86400.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "week", "symbol": "wk", "type": "time", "base_unit": "second", "conversion_factor": 604800.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "month", "symbol": "mo", "type": "time", "base_unit": "second", "conversion_factor": 2592000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
        {"name": "year", "symbol": "yr", "type": "time", "base_unit": "second", "conversion_factor": 31536000.0, "is_custom": False, "is_mapped": True, "created_by": None, "created_at": datetime.utcnow()},
    ]

    # Seed regular units
    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))

    db.session.commit()
