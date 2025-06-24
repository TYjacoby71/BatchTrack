
from ..models import Unit
from ..extensions import db

def seed_units():
    units = [
        # Weight Units
        {"name": "gram", "symbol": "g", "type": "weight", "base_unit": "gram", "conversion_factor": 1.0},
        {"name": "kg", "symbol": "kg", "type": "weight", "base_unit": "gram", "conversion_factor": 1000.0},
        {"name": "mg", "symbol": "mg", "type": "weight", "base_unit": "gram", "conversion_factor": 0.001},
        {"name": "oz", "symbol": "oz", "type": "weight", "base_unit": "gram", "conversion_factor": 28.3495},
        {"name": "lb", "symbol": "lb", "type": "weight", "base_unit": "gram", "conversion_factor": 453.592},
        {"name": "ton", "symbol": "ton", "type": "weight", "base_unit": "gram", "conversion_factor": 907184.74},

        # Volume Units
        {"name": "ml", "symbol": "ml", "type": "volume", "base_unit": "ml", "conversion_factor": 1.0},
        {"name": "liter", "symbol": "L", "type": "volume", "base_unit": "ml", "conversion_factor": 1000.0},
        {"name": "tsp", "symbol": "tsp", "type": "volume", "base_unit": "ml", "conversion_factor": 4.92892},
        {"name": "tbsp", "symbol": "tbsp", "type": "volume", "base_unit": "ml", "conversion_factor": 14.7868},
        {"name": "cup", "symbol": "cup", "type": "volume", "base_unit": "ml", "conversion_factor": 236.588},
        {"name": "pint", "symbol": "pt", "type": "volume", "base_unit": "ml", "conversion_factor": 473.176},
        {"name": "quart", "symbol": "qt", "type": "volume", "base_unit": "ml", "conversion_factor": 946.353},
        {"name": "gallon", "symbol": "gal", "type": "volume", "base_unit": "ml", "conversion_factor": 3785.41},
        {"name": "floz", "symbol": "fl oz", "type": "volume", "base_unit": "ml", "conversion_factor": 29.5735},
        {"name": "drop", "symbol": "drop", "type": "volume", "base_unit": "ml", "conversion_factor": 0.05},
        {"name": "dram", "symbol": "dram", "type": "volume", "base_unit": "ml", "conversion_factor": 3.69669},

        # Length Units
        {"name": "cm", "symbol": "cm", "type": "length", "base_unit": "cm", "conversion_factor": 1.0},
        {"name": "mm", "symbol": "mm", "type": "length", "base_unit": "cm", "conversion_factor": 0.1},
        {"name": "inch", "symbol": "in", "type": "length", "base_unit": "cm", "conversion_factor": 2.54},
        {"name": "ft", "symbol": "ft", "type": "length", "base_unit": "cm", "conversion_factor": 30.48},
        {"name": "yard", "symbol": "yd", "type": "length", "base_unit": "cm", "conversion_factor": 91.44},
        {"name": "meter", "symbol": "m", "type": "length", "base_unit": "cm", "conversion_factor": 100.0},

        # Area Units
        {"name": "sqcm", "symbol": "cm²", "type": "area", "base_unit": "sqcm", "conversion_factor": 1.0},
        {"name": "sqm", "symbol": "m²", "type": "area", "base_unit": "sqcm", "conversion_factor": 10000.0},
        {"name": "sqinch", "symbol": "in²", "type": "area", "base_unit": "sqcm", "conversion_factor": 6.4516},
        {"name": "sqft", "symbol": "ft²", "type": "area", "base_unit": "sqcm", "conversion_factor": 929.03},
        {"name": "sqyard", "symbol": "yd²", "type": "area", "base_unit": "sqcm", "conversion_factor": 8361.27},
        {"name": "acre", "symbol": "acre", "type": "area", "base_unit": "sqcm", "conversion_factor": 40468564.0},

        # Cubic Volume Units
        {"name": "cubicinch", "symbol": "in³", "type": "volume", "base_unit": "ml", "conversion_factor": 16.3871},
        {"name": "cubicfoot", "symbol": "ft³", "type": "volume", "base_unit": "ml", "conversion_factor": 28316.8},
        {"name": "cubicyard", "symbol": "yd³", "type": "volume", "base_unit": "ml", "conversion_factor": 764555.0},

        # Count Units
        {"name": "count", "symbol": "ct", "type": "count", "base_unit": "count", "conversion_factor": 1.0},
        {"name": "pack", "symbol": "pk", "type": "count", "base_unit": "count", "conversion_factor": 1.0},
        {"name": "dozen", "symbol": "dz", "type": "count", "base_unit": "count", "conversion_factor": 12.0},
        {"name": "unit", "symbol": "unit", "type": "count", "base_unit": "count", "conversion_factor": 1.0},
        {"name": "batch", "symbol": "batch", "type": "count", "base_unit": "count", "conversion_factor": 1.0},
        {"name": "pair", "symbol": "pair", "type": "count", "base_unit": "count", "conversion_factor": 2.0},

        # Time Units
        {"name": "second", "symbol": "s", "type": "time", "base_unit": "second", "conversion_factor": 1.0},
        {"name": "minute", "symbol": "min", "type": "time", "base_unit": "second", "conversion_factor": 60.0},
        {"name": "hour", "symbol": "hr", "type": "time", "base_unit": "second", "conversion_factor": 3600.0},
        {"name": "day", "symbol": "day", "type": "time", "base_unit": "second", "conversion_factor": 86400.0},
        {"name": "week", "symbol": "wk", "type": "time", "base_unit": "second", "conversion_factor": 604800.0},
        {"name": "month", "symbol": "mo", "type": "time", "base_unit": "second", "conversion_factor": 2592000.0},
        {"name": "year", "symbol": "yr", "type": "time", "base_unit": "second", "conversion_factor": 31536000.0},
    ]

    # Seed regular units
    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))

    db.session.commit()
