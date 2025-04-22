from app import app, db  # Ensure db is bound via app.py
from models import User, Unit, IngredientCategory
from werkzeug.security import generate_password_hash

def seed_units():
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

        # Cubic Volume Units
        {"name": "cubicinch", "type": "volume", "base_unit": "ml", "multiplier_to_base": 16.3871},
        {"name": "cubicfoot", "type": "volume", "base_unit": "ml", "multiplier_to_base": 28316.8},
        {"name": "cubicyard", "type": "volume", "base_unit": "ml", "multiplier_to_base": 764555.0},

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
    ]

    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))


def seed_categories():
    categories = [
        # Core
        {"name": "Liquid", "default_density": 1.0},
        {"name": "Oil", "default_density": 0.92},
        {"name": "Solid", "default_density": 0.8},
        {"name": "Powder", "default_density": 0.5},
        {"name": "Dairy", "default_density": 1.03},
        {"name": "Syrup", "default_density": 1.33},

        # Specialty
        {"name": "Alcohol", "default_density": 0.789},
        {"name": "Fragrance", "default_density": 0.86},
        {"name": "Gel", "default_density": 1.05},
        {"name": "Wax", "default_density": 0.9},
        {"name": "Extract", "default_density": 1.1},
        {"name": "Clay", "default_density": 1.6},
        {"name": "Other", "default_density": 1.0},
    ]

    for cat in categories:
        if not IngredientCategory.query.filter_by(name=cat["name"]).first():
            db.session.add(IngredientCategory(**cat))


def init_db():
    with app.app_context():
        db.create_all()
        seed_units()
        seed_categories()

        # Default admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin)

        db.session.commit()
        print("✅ Database initialized with units, categories, and admin user.")


if __name__ == "__main__":
    init_db()
