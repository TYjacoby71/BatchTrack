from models import IngredientCategory, db, InventoryItem # Added import for InventoryItem

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
        {"name": "Container", "default_density": 1.0} # Added Container Category
    ]

    for category in categories:
        if not IngredientCategory.query.filter_by(name=category["name"]).first():
            db.session.add(IngredientCategory(**category))

    db.session.commit()

    # Update all items in Container category to have type='container'
    container_cat = IngredientCategory.query.filter_by(name='Container').first()
    if container_cat:
        items = InventoryItem.query.filter_by(category_id=container_cat.id).all()
        for item in items:
            item.type = 'container'
        db.session.commit()