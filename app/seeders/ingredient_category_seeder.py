
from ..models import IngredientCategory, InventoryItem
from ..extensions import db

def seed_categories():
    categories = [
        # Core Categories
        {"name": "Liquid"},             # Water, vinegar, juices
        {"name": "Oil"},               # Olive, coconut, canola
        {"name": "Solid"},              # Soap base, butter blocks
        {"name": "Powder"},             # Flour, clay powder, mica
        {"name": "Dairy"},             # Milk, cream, yogurt
        {"name": "Syrup"},             # Honey, agave, glucose

        # Specialty Categories
        {"name": "Alcohol"},          # Ethanol, isopropyl, tinctures
        {"name": "Fragrance"},         # Essential oils, perfume
        {"name": "Gel"},               # Aloe gel, cosmetic bases
        {"name": "Wax"},                # Beeswax, soy wax, paraffin
        {"name": "Extract"},            # Vanilla, herbal extracts
        {"name": "Clay"},               # Bentonite, kaolin
        {"name": "Other"},              # Catch-all or uncategorized
        {"name": "Container"}           # Added Container Category
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
