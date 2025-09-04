
from flask_login import current_user
from ..models import IngredientCategory, InventoryItem
from ..extensions import db

def seed_categories(organization_id=None):
    # Use provided organization_id or current user's org
    if organization_id is None and current_user and current_user.is_authenticated:
        organization_id = current_user.organization_id
    
    if not organization_id:
        raise ValueError("Organization ID required for seeding categories")
    
    categories = [
        # Match density_reference.json categories exactly
        {"name": "Liquids", "organization_id": organization_id, "default_density": 1.0},
        {"name": "Dairy", "organization_id": organization_id, "default_density": 1.02},
        {"name": "Oils", "organization_id": organization_id, "default_density": 0.92},
        {"name": "Fats", "organization_id": organization_id, "default_density": 0.91},
        {"name": "Syrups", "organization_id": organization_id, "default_density": 1.4},
        {"name": "Flours", "organization_id": organization_id, "default_density": 0.6},
        {"name": "Starches", "organization_id": organization_id, "default_density": 0.63},
        {"name": "Sugars", "organization_id": organization_id, "default_density": 0.85},
        {"name": "Sweeteners", "organization_id": organization_id, "default_density": 0.67},
        {"name": "Salts", "organization_id": organization_id, "default_density": 2.16},
        {"name": "Leavening", "organization_id": organization_id, "default_density": 1.56},
        {"name": "Chocolate", "organization_id": organization_id, "default_density": 0.71},
        {"name": "Spices", "organization_id": organization_id, "default_density": 0.57},
        {"name": "Herbs", "organization_id": organization_id, "default_density": 0.32},
        {"name": "Extracts", "organization_id": organization_id, "default_density": 0.86},
        {"name": "Acids", "organization_id": organization_id, "default_density": 1.03},
        {"name": "Grains", "organization_id": organization_id, "default_density": 0.72},
        {"name": "Nuts", "organization_id": organization_id, "default_density": 0.55},
        {"name": "Seeds", "organization_id": organization_id, "default_density": 0.61},
        {"name": "Dried Fruits", "organization_id": organization_id, "default_density": 0.69},
        {"name": "Waxes", "organization_id": organization_id, "default_density": 0.93},
        {"name": "Clays", "organization_id": organization_id, "default_density": 2.45},
        {"name": "Essential Oils", "organization_id": organization_id, "default_density": 0.89},
        {"name": "Cosmetic Ingredients", "organization_id": organization_id, "default_density": 1.08},
        {"name": "Alcohols", "organization_id": organization_id, "default_density": 0.85},
        {"name": "Container", "organization_id": organization_id, "default_density": None},  # Special category for containers
        {"name": "Other", "organization_id": organization_id, "default_density": 1.0}        # Catch-all category
    ]

    for category in categories:
        # Check if category already exists for this organization
        existing = IngredientCategory.query.filter_by(
            name=category["name"], 
            organization_id=organization_id
        ).first()
        if not existing:
            db.session.add(IngredientCategory(**category))
        else:
            # Update existing category with new density value if it's missing
            if existing.default_density is None and category.get("default_density") is not None:
                existing.default_density = category["default_density"]

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
