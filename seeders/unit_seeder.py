
from models import Unit, db

def seed_units():
    units = [
        # Weight Units
        {"name": "µg", "type": "weight", "base_unit": "gram", "multiplier_to_base": 0.000001},
        {"name": "mg", "type": "weight", "base_unit": "gram", "multiplier_to_base": 0.001},
        {"name": "gram", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1.0},
        {"name": "kg", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1000.0},
        {"name": "oz", "type": "weight", "base_unit": "gram", "multiplier_to_base": 28.3495},
        {"name": "lb", "type": "weight", "base_unit": "gram", "multiplier_to_base": 453.592},
        {"name": "melt", "type": "weight", "base_unit": "gram", "multiplier_to_base": 15.0},

        # Volume Units
        {"name": "µl", "type": "volume", "base_unit": "ml", "multiplier_to_base": 0.001},
        {"name": "drop", "type": "volume", "base_unit": "ml", "multiplier_to_base": 0.05},
        {"name": "dash", "type": "volume", "base_unit": "ml", "multiplier_to_base": 0.6},
        {"name": "shot", "type": "volume", "base_unit": "ml", "multiplier_to_base": 44.36},
        {"name": "ml", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1.0},
        {"name": "liter", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1000.0},
        {"name": "tsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 4.92892},
        {"name": "tbsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 14.7868},
        {"name": "cup", "type": "volume", "base_unit": "ml", "multiplier_to_base": 236.588},
        {"name": "pint", "type": "volume", "base_unit": "ml", "multiplier_to_base": 473.176},
        {"name": "quart", "type": "volume", "base_unit": "ml", "multiplier_to_base": 946.353},
        {"name": "fl oz", "type": "volume", "base_unit": "ml", "multiplier_to_base": 29.5735},
        {"name": "cube", "type": "volume", "base_unit": "ml", "multiplier_to_base": 15.0},

        # Length Units  
        {"name": "mm", "type": "length", "base_unit": "cm", "multiplier_to_base": 0.1},
        {"name": "cm", "type": "length", "base_unit": "cm", "multiplier_to_base": 1.0},
        {"name": "inch", "type": "length", "base_unit": "cm", "multiplier_to_base": 2.54},
        {"name": "foot", "type": "length", "base_unit": "cm", "multiplier_to_base": 30.48},
        {"name": "meter", "type": "length", "base_unit": "cm", "multiplier_to_base": 100.0},

        # Area Units
        {"name": "sqcm", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 1.0},
        {"name": "sqin", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 6.4516},
        {"name": "sqft", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 929.03},
        {"name": "sqm", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 10000.0},

        # Count Units
        {"name": "count", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "unit", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "pack", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "dozen", "type": "count", "base_unit": "count", "multiplier_to_base": 12.0},
        {"name": "spritz", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "swipe", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "bar", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},

        # Time Units
        {"name": "second", "type": "time", "base_unit": "second", "multiplier_to_base": 1.0},
        {"name": "minute", "type": "time", "base_unit": "second", "multiplier_to_base": 60.0},
        {"name": "hour", "type": "time", "base_unit": "second", "multiplier_to_base": 3600.0},
        {"name": "day", "type": "time", "base_unit": "second", "multiplier_to_base": 86400.0},
    ]

    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))
    db.session.commit()
