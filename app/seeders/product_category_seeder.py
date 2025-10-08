from app.extensions import db
from app.models.product_category import ProductCategory


DEFAULT_CATEGORIES = [
    # Portioned categories use derivative portion size attributes
    {"name": "Soaps", "is_portioned": True,  "template": "{variant} {product} ({portion_size_value} {portion_size_unit} {portion_name})"},
    {"name": "Baked Goods", "is_portioned": True,  "template": "{variant} {product} ({portion_size_value} {portion_size_unit} {portion_name})"},
    {"name": "Confectionery", "is_portioned": True,  "template": "{variant} {product} ({portion_size_value} {portion_size_unit} {portion_name})"},

    # Container-defined categories use the container-derived label
    {"name": "Candles", "is_portioned": False, "template": "{variant} {product} ({container})"},
    {"name": "Cosmetics", "is_portioned": False, "template": "{variant} {product} ({container})"},
    {"name": "Preserves", "is_portioned": False, "template": "{variant} {product} ({container})"},
    {"name": "Beverages", "is_portioned": False, "template": "{variant} {product} ({container})"},
    {"name": "Miscellaneous", "is_portioned": False, "template": "{variant} {product} ({container})"},
]


def seed_product_categories():
    for row in DEFAULT_CATEGORIES:
        existing = ProductCategory.query.filter(ProductCategory.name.ilike(row["name"])) .first()
        if not existing:
            ui_config = None
            if row["name"] == 'Soaps':
                ui_config = {"overlay": "soap", "unit_mode": "weight"}
            elif row["name"] == 'Baked Goods':
                ui_config = {"overlay": "baking", "unit_mode": "weight"}
            elif row["name"] == 'Candles':
                ui_config = {"overlay": "candle", "unit_mode": "weight", "supports_fill_pct": True}
            elif row["name"] == 'Cosmetics':
                ui_config = {"overlay": "lotion", "unit_mode": "weight"}
            else:
                ui_config = None
            db.session.add(ProductCategory(name=row["name"], is_typically_portioned=row["is_portioned"], sku_name_template=row["template"], ui_config=ui_config))
        else:
            # update template/flag if changed
            changed = False
            if existing.is_typically_portioned != row["is_portioned"]:
                existing.is_typically_portioned = row["is_portioned"]
                changed = True
            if not existing.sku_name_template:
                existing.sku_name_template = row["template"]
                changed = True
            # Only set ui_config if empty
            if not getattr(existing, 'ui_config', None):
                if row["name"] == 'Soaps':
                    existing.ui_config = {"overlay": "soap", "unit_mode": "weight"}
                    changed = True
                elif row["name"] == 'Baked Goods':
                    existing.ui_config = {"overlay": "baking", "unit_mode": "weight"}
                    changed = True
                elif row["name"] == 'Candles':
                    existing.ui_config = {"overlay": "candle", "unit_mode": "weight", "supports_fill_pct": True}
                    changed = True
                elif row["name"] == 'Cosmetics':
                    existing.ui_config = {"overlay": "lotion", "unit_mode": "weight"}
                    changed = True
            if changed:
                db.session.add(existing)
    db.session.commit()

