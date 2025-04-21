
from models import Unit, db

def seed_units():
    units = [
        {"name": "gram", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1.0},
        {"name": "kg", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1000.0},
        {"name": "oz", "type": "weight", "base_unit": "gram", "multiplier_to_base": 28.3495},
        {"name": "lb", "type": "weight", "base_unit": "gram", "multiplier_to_base": 453.592},
        {"name": "ml", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1.0},
        {"name": "liter", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1000.0},
        {"name": "tsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 4.92892},
        {"name": "tbsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 14.7868},
        {"name": "cup", "type": "volume", "base_unit": "ml", "multiplier_to_base": 236.588},
        {"name": "count", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "pack", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "cm", "type": "length", "base_unit": "cm", "multiplier_to_base": 1.0},
        {"name": "inch", "type": "length", "base_unit": "cm", "multiplier_to_base": 2.54},
        {"name": "sqcm", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 1.0},
        {"name": "sqft", "type": "area", "base_unit": "sqcm", "multiplier_to_base": 929.03},
        {"name": "scoop", "type": "volume", "base_unit": "ml", "multiplier_to_base": 50.0},
        {"name": "pinch", "type": "weight", "base_unit": "gram", "multiplier_to_base": 0.5},
    ]
    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))
    db.session.commit()