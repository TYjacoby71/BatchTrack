
from flask_login import current_user
from ..models import IngredientCategory, InventoryItem
from ..extensions import db

def seed_categories(organization_id=None):
    # Use provided organization_id or current user's org
    if organization_id is None and current_user.is_authenticated:
        organization_id = current_user.organization_id
    
    if not organization_id:
        raise ValueError("Organization ID required for seeding categories")
    
    categories = [
        # Core Categories
        {"name": "Liquid", "organization_id": organization_id},             # Water, vinegar, juices
        {"name": "Oil", "organization_id": organization_id},               # Olive, coconut, canola
        {"name": "Solid", "organization_id": organization_id},              # Soap base, butter blocks
        {"name": "Powder", "organization_id": organization_id},             # Flour, clay powder, mica
        {"name": "Dairy", "organization_id": organization_id},             # Milk, cream, yogurt
        {"name": "Syrup", "organization_id": organization_id},             # Honey, agave, glucose

        # Specialty Categories
        {"name": "Alcohol", "organization_id": organization_id},          # Ethanol, isopropyl, tinctures
        {"name": "Fragrance", "organization_id": organization_id},         # Essential oils, perfume
        {"name": "Gel", "organization_id": organization_id},               # Aloe gel, cosmetic bases
        {"name": "Wax", "organization_id": organization_id},                # Beeswax, soy wax, paraffin
        {"name": "Extract", "organization_id": organization_id},            # Vanilla, herbal extracts
        {"name": "Clay", "organization_id": organization_id},               # Bentonite, kaolin
        {"name": "Other", "organization_id": organization_id},              # Catch-all or uncategorized
        {"name": "Container", "organization_id": organization_id}           # Added Container Category
    ]

    for category in categories:
        # Check if category already exists for this organization
        existing = IngredientCategory.query.filter_by(
            name=category["name"], 
            organization_id=organization_id
        ).first()
        if not existing:
            db.session.add(IngredientCategory(**category))

    db.session.commit()

    # Update all items in Container category to have type='container'
    container_cat = IngredientCategory.query.filter_by(
        name='Container', 
        organization_id=organization_id
    ).first()
    if container_cat:
        items = InventoryItem.query.filter_by(
            category_id=container_cat.id,
            organization_id=organization_id
        ).all()
        for item in items:
            item.type = 'container'
        db.session.commit()
