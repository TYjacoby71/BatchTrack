
from models import IngredientCategory, db

def seed_categories():
    categories = [
        {"name": "Oil", "default_density": 0.92},
        {"name": "Liquid", "default_density": 1.0},
        {"name": "Solid", "default_density": 0.8},
        {"name": "Powder", "default_density": 0.5},
        {"name": "Dairy", "default_density": 1.03},
        {"name": "Syrup", "default_density": 1.33},
    ]

    for category in categories:
        if not IngredientCategory.query.filter_by(name=category["name"]).first():
            new_cat = IngredientCategory(**category)
            db.session.add(new_cat)
    db.session.commit()
