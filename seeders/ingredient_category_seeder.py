
from models import IngredientCategory, db

def seed_categories():
    categories = [
        # Core Categories
        {"name": "Liquid", "default_density": 1.0},             # Water, vinegar, juices
        {"name": "Oil", "default_density": 0.92},               # Olive, coconut, canola
        {"name": "Solid", "default_density": 0.8},              # Soap base, butter blocks
        {"name": "Powder", "default_density": 0.5},             # Flour, clay powder, mica
        {"name": "Dairy", "default_density": 1.03},             # Milk, cream, yogurt
        {"name": "Syrup", "default_density": 1.33},             # Honey, agave, glucose

        # Specialty Categories
        {"name": "Alcohol", "default_density": 0.789},          # Ethanol, isopropyl, tinctures
        {"name": "Fragrance", "default_density": 0.86},         # Essential oils, perfume
        {"name": "Gel", "default_density": 1.05},               # Aloe gel, cosmetic bases
        {"name": "Wax", "default_density": 0.9},                # Beeswax, soy wax, paraffin
        {"name": "Extract", "default_density": 1.1},            # Vanilla, herbal extracts
        {"name": "Clay", "default_density": 1.6},               # Bentonite, kaolin
        {"name": "Other", "default_density": 1.0},              # Catch-all or uncategorized
    ]

    for cat in categories:
        if not IngredientCategory.query.filter_by(name=cat["name"]).first():
            db.session.add(IngredientCategory(**cat))

    db.session.commit()
