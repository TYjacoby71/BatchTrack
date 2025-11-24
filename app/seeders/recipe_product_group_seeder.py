import re

from app.extensions import db
from app.models.recipe_marketplace import RecipeProductGroup


DEFAULT_GROUPS = [
    ("Bar Soap", "soap", "Traditional cold & hot process soap bars for face and body."),
    ("Liquid Soap", "tint", "High-clarity liquid soaps, castile bases, and body washes."),
    ("Lotion & Creams", "pump", "Emulsified lotions, creams, and leave-on moisturizers."),
    ("Body Butter", "jar", "Anhydrous whipped butters and concentrated moisturizers."),
    ("Balms & Salves", "band-aid", "Targeted balms, salves, and solid treatment sticks."),
    ("Candle & Wax Melts", "fire", "Container candles, pillars, wax melts, and fragrance bars."),
    ("Tallow Goods", "drumstick", "Soaps, balms, and skincare centered on rendered fats."),
    ("Bakery & Breads", "bread-slice", "Loaves, sourdough, focaccia, and enriched breads."),
    ("Pies & Pastries", "pie", "Sweet pies, turnovers, and laminated pastry favorites."),
    ("Confectionery & Candy", "candy-cane", "Caramels, brittles, fudge, and sugar-work recipes."),
    ("Beverage & Syrups", "mug", "Syrups, shrubs, concentrates, and tea latte bases."),
    ("Fragrance & Room Mists", "spray-can", "Fine fragrance sprays, body mists, and linen refreshers."),
    ("Herbal Infusions", "seedling", "Oil macerations, tinctures, and botanical infusions."),
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")


def seed_recipe_product_groups():
    print("🌿 Seeding recipe product groups...")
    created = 0
    updated = 0

    for order, (name, icon, description) in enumerate(DEFAULT_GROUPS, start=1):
        slug = _slugify(name)
        record = RecipeProductGroup.query.filter(
            (RecipeProductGroup.slug == slug) | (RecipeProductGroup.name.ilike(name))
        ).first()

        if not record:
            record = RecipeProductGroup(
                name=name,
                slug=slug,
                description=description,
                icon=icon,
                display_order=order,
                is_active=True,
            )
            db.session.add(record)
            created += 1
            print(f"   ✅ Created group {name}")
        else:
            changed = False
            if record.description != description:
                record.description = description
                changed = True
            if record.icon != icon:
                record.icon = icon
                changed = True
            if record.display_order != order:
                record.display_order = order
                changed = True
            if not record.is_active:
                record.is_active = True
                changed = True
            if changed:
                db.session.add(record)
                updated += 1
                print(f"   ↻ Updated group {name}")

    try:
        db.session.commit()
        print(f"✨ Recipe product groups seeded (created: {created}, updated: {updated})")
    except Exception as exc:
        db.session.rollback()
        print(f"❌ Failed to seed recipe product groups: {exc}")
        raise
