from app.extensions import db
from app.models.product_category import ProductCategory


DEFAULT_CATEGORIES = [
    ("Uncategorized", False),
    ("Soaps", True),
    ("Candles", False),
    ("Cosmetics", False),
    ("Baked Goods", True),
    ("Brewing", False),
    ("Confectionery", True),
    ("Bath Bombs", True),
    ("Skincare", False),
]


def seed_product_categories():
    for name, portioned in DEFAULT_CATEGORIES:
        existing = ProductCategory.query.filter(ProductCategory.name.ilike(name)).first()
        if not existing:
            db.session.add(ProductCategory(name=name, is_typically_portioned=portioned))
    db.session.commit()

