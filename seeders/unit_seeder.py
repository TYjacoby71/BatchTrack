
from models import Unit, db

def seed_units():
    # Product units for batch output
    product_units = [
        {"name": "box", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "bottle", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "jar", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "tube", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "tin", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "pouch", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "sachet", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "pack", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0},
        {"name": "kit", "type": "product", "base_unit": "box", "multiplier_to_base": 1.0}
    ]

    units = [
        # Weight Units
        {"name": "gram", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1.0},
        {"name": "kg", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1000.0},
        {"name": "mg", "type": "weight", "base_unit": "gram", "multiplier_to_base": 0.001},
        {"name": "oz", "type": "weight", "base_unit": "gram", "multiplier_to_base": 28.3495},
        {"name": "lb", "type": "weight", "base_unit": "gram", "multiplier_to_base": 453.592},
        {"name": "ton", "type": "weight", "base_unit": "gram", "multiplier_to_base": 907184.74},

        # Volume Units
        {"name": "ml", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1.0},
        {"name": "liter", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1000.0},
        {"name": "tsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 4.92892},
        {"name": "tbsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 14.7868},
        {"name": "cup", "type": "volume", "base_unit": "ml", "multiplier_to_base": 236.588},
        {"name": "pint", "type": "volume", "base_unit": "ml", "multiplier_to_base": 473.176},
        {"name": "quart", "type": "volume", "base_unit": "ml", "multiplier_to_base": 946.353},
        {"name": "gallon", "type": "volume", "base_unit": "ml", "multiplier_to_base": 3785.41},
        {"name": "floz", "type": "volume", "base_unit": "ml", "multiplier_to_base": 29.5735},
        {"name": "drop", "type": "volume", "base_unit": "ml", "multiplier_to_base": 0.05},
        {"name": "dram", "type": "volume", "base_unit": "ml", "multiplier_to_base": 3.69669},

        # Length Units
        {"name": "cm", "type": "length", "base_unit": "cm", "multiplier_to_base": 1.0},
        {"name": "mm", "type": "length", "base_unit": "cm", "multiplier_to_base": 0.1},
        {"name": "inch", "type": "length", "base_unit": "cm", "multiplier_to_base": 2.54},
        {"name": "ft", "type": "length", "base_unit": "cm", "multiplier_to_base": 30.48},
        {"name": "yard", "type": "length", "base_unit": "cm", "multiplier_to_base": 91.44},
        {"name": "meter", "type": "length", "base_unit": "cm", "multiplier_to_base": 100.0},

        # Area Units
        {"name": "sqcm", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 1.0},
        {"name": "sqm", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 10000.0},
        {"name": "sqinch", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 6.4516},
        {"name": "sqft", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 929.03},
        {"name": "sqyard", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 8361.27},
        {"name": "acre", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 40468564.0},

        # Cubic Volume Units
        {"name": "cubicinch", "type": "volume", "base_unit": "ml", "multiplier_to_base": 16.3871},
        {"name": "cubicfoot", "type": "volume", "base_unit": "ml", "multiplier_to_base": 28316.8},
        {"name": "cubicyard", "type": "volume", "base_unit": "ml", "multiplier_to_base": 764555.0},

        # Count Units
        {"name": "count", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "pack", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "dozen", "type": "count", "base_unit": "count", "multiplier_to_base": 12.0},
        {"name": "unit", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "batch", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "pair", "type": "count", "base_unit": "count", "multiplier_to_base": 2.0},

        # Time Units
        {"name": "second", "type": "time", "base_unit": "second", "multiplier_to_base": 1.0},
        {"name": "minute", "type": "time", "base_unit": "second", "multiplier_to_base": 60.0},
        {"name": "hour", "type": "time", "base_unit": "second", "multiplier_to_base": 3600.0},
        {"name": "day", "type": "time", "base_unit": "second", "multiplier_to_base": 86400.0},
        {"name": "week", "type": "time", "base_unit": "second", "multiplier_to_base": 604800.0},
        {"name": "month", "type": "time", "base_unit": "second", "multiplier_to_base": 2592000.0},
        {"name": "year", "type": "time", "base_unit": "second", "multiplier_to_base": 31536000.0},
    ]

    # Seed regular units
    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))

    # Seed product units
    for unit in product_units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))
            
    db.session.commit()
