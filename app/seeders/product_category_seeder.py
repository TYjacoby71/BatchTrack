from app.extensions import db
from app.models.product_category import ProductCategory

DEFAULT_CATEGORIES = [
    # Portioned categories use derivative portion size attributes
    {
        "name": "Soaps",
        "is_portioned": True,
        "template": "{variant} {product} ({portion_size_value} {portion_size_unit} {portion_name})",
    },
    {
        "name": "Baked Goods",
        "is_portioned": True,
        "template": "{variant} {product} ({portion_size_value} {portion_size_unit} {portion_name})",
    },
    {
        "name": "Confectionery",
        "is_portioned": True,
        "template": "{variant} {product} ({portion_size_value} {portion_size_unit} {portion_name})",
    },
    # Container-defined categories use the container-derived label
    {
        "name": "Candles",
        "is_portioned": False,
        "template": "{variant} {product} ({container})",
    },
    {
        "name": "Cosmetics",
        "is_portioned": False,
        "template": "{variant} {product} ({container})",
    },
    {
        "name": "Preserves",
        "is_portioned": False,
        "template": "{variant} {product} ({container})",
    },
    {
        "name": "Beverages",
        "is_portioned": False,
        "template": "{variant} {product} ({container})",
    },
    {
        "name": "Miscellaneous",
        "is_portioned": False,
        "template": "{variant} {product} ({container})",
    },
    # Add Uncategorized as default fallback category
    {"name": "Uncategorized", "is_portioned": False, "template": "{variant} {product}"},
]


def seed_product_categories():
    """Seed default product categories"""
    print("🔧 Seeding product categories...")

    categories_created = 0
    categories_updated = 0

    for row in DEFAULT_CATEGORIES:
        existing = ProductCategory.query.filter(
            ProductCategory.name.ilike(row["name"])
        ).first()

        if not existing:
            # Create new category
            new_category = ProductCategory(
                name=row["name"],
                is_typically_portioned=row["is_portioned"],
                sku_name_template=row["template"],
                skin_enabled=False,
            )
            db.session.add(new_category)
            categories_created += 1
            print(f"   ✅ Created category: {row['name']}")
        else:
            # Update existing category if needed
            changed = False
            if existing.is_typically_portioned != row["is_portioned"]:
                existing.is_typically_portioned = row["is_portioned"]
                changed = True
            if not existing.sku_name_template:
                existing.sku_name_template = row["template"]
                changed = True
            if existing.skin_enabled is None:
                existing.skin_enabled = False
                changed = True

            if changed:
                db.session.add(existing)
                categories_updated += 1
                print(f"   ↻ Updated category: {row['name']}")
            else:
                print(f"   ↻ Category exists: {row['name']}")

    try:
        db.session.commit()
        print(
            f"✅ Product categories seeded successfully! (Created: {categories_created}, Updated: {categories_updated})"
        )
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error seeding product categories: {e}")
        raise
