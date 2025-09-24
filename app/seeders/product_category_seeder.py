from app.extensions import db
from app.models.product_category import ProductCategory


DEFAULT_CATEGORIES = [
    {"name": "Soaps", "is_portioned": True,  "template": "{variant} {product} ({size_label})"},
    {"name": "Candles", "is_portioned": False, "template": "{variant} {product} ({container})"},
    {"name": "Cosmetics", "is_portioned": False, "template": "{container} of {variant} {product}"},
    {"name": "Baked Goods", "is_portioned": True,  "template": "{variant} {product} ({size_label})"},
    {"name": "Preserves", "is_portioned": False, "template": "{container} of {variant} {product}"},
    {"name": "Beverages", "is_portioned": False, "template": "{container} of {variant} {product}"},
    {"name": "Confectionery", "is_portioned": True,  "template": "{variant} {product} ({size_label})"},
    {"name": "Miscellaneous", "is_portioned": False, "template": "{container} of {variant} {product}"},
]


def seed_product_categories():
    for row in DEFAULT_CATEGORIES:
        existing = ProductCategory.query.filter(ProductCategory.name.ilike(row["name"])) .first()
        if not existing:
            db.session.add(ProductCategory(name=row["name"], is_typically_portioned=row["is_portioned"], sku_name_template=row["template"]))
        else:
            # update template/flag if changed
            changed = False
            if existing.is_typically_portioned != row["is_portioned"]:
                existing.is_typically_portioned = row["is_portioned"]
                changed = True
            if not existing.sku_name_template:
                existing.sku_name_template = row["template"]
                changed = True
            if changed:
                db.session.add(existing)
    db.session.commit()

