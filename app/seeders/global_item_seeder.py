from ..extensions import db
from ..models import GlobalItem, IngredientCategory

import json
import os


def _load_density_json():
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, 'data', 'density_reference.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def _load_category_files():
    base_path = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')
    categories = []
    if not os.path.exists(base_path):
        return categories
    for filename in os.listdir(base_path):
        if filename.endswith('.json'):
            filepath = os.path.join(base_path, filename)
            try:
                with open(filepath, 'r') as f:
                    category_data = json.load(f)
                    categories.append(category_data)
            except Exception as e:
                print(f"⚠️  Error loading {filename}: {e}")
    return categories


def seed_global_items():
    """Seed curated global ingredient categories and global items.

    - Creates/updates curated `IngredientCategory` with organization_id=None
    - Upserts `GlobalItem` rows and links to curated categories
    - Uses JSON files in app/seeders/globallist and optional data/density_reference.json
    """
    created_categories = 0
    created_items = 0
    updated_items = 0

    # Load curated category files
    categories = _load_category_files()

    for cat_data in categories:
        cat_name = (cat_data.get('category_name') or '').strip()
        if not cat_name:
            continue
        default_density = cat_data.get('default_density')
        description = cat_data.get('description', '')

        curated_cat = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
        if not curated_cat:
            curated_cat = IngredientCategory(
                name=cat_name,
                description=description,
                default_density=default_density,
                is_global_category=True,
                organization_id=None,
                is_active=True
            )
            db.session.add(curated_cat)
            db.session.flush()
            created_categories += 1
        else:
            if default_density is not None and curated_cat.default_density is None:
                curated_cat.default_density = default_density
            if description:
                curated_cat.description = description
            curated_cat.is_global_category = True

        for item_data in cat_data.get('items', []):
            name = (item_data.get('name') or '').strip()
            if not name:
                continue
            density = item_data.get('density_g_per_ml')
            aka = item_data.get('aka', [])
            default_unit = item_data.get('default_unit')
            perishable = item_data.get('perishable', False)
            shelf_life_days = item_data.get('shelf_life_days')

            existing = GlobalItem.query.filter_by(name=name, item_type='ingredient').first()
            if existing:
                existing.density = density
                existing.aka_names = aka
                existing.default_unit = default_unit
                existing.ingredient_category_id = curated_cat.id
                existing.default_is_perishable = perishable
                existing.recommended_shelf_life_days = shelf_life_days
                updated_items += 1
            else:
                gi = GlobalItem(
                    name=name,
                    item_type='ingredient',
                    default_unit=default_unit,
                    density=density,
                    ingredient_category_id=curated_cat.id,
                    aka_names=aka,
                    default_is_perishable=perishable,
                    recommended_shelf_life_days=shelf_life_days,
                )
                db.session.add(gi)
                created_items += 1

    db.session.commit()
    print(f"✅ Curated categories created: {created_categories}; Items created: {created_items}; Items updated: {updated_items}")

    # Process legacy density_reference.json if present
    payload = _load_density_json()
    if payload and 'common_densities' in payload:
        default_map = {
            'Liquids': 1.0,
            'Dairy': 1.02,
            'Oils': 0.92,
            'Fats': 0.91,
            'Syrups': 1.4,
            'Flours': 0.6,
            'Starches': 0.63,
            'Sugars': 0.85,
            'Sweeteners': 0.67,
            'Salts': 2.16,
            'Leavening': 1.56,
            'Chocolate': 0.71,
            'Spices': 0.57,
            'Herbs': 0.32,
            'Extracts': 0.86,
            'Acids': 1.03,
            'Grains': 0.72,
            'Nuts': 0.55,
            'Seeds': 0.61,
            'Dried Fruits': 0.69,
            'Waxes': 0.93,
            'Clays': 2.45,
            'Essential Oils': 0.89,
            'Cosmetic Ingredients': 1.08,
            'Alcohols': 0.85,
        }

        items = payload.get('common_densities', [])

        for it in items:
            cat_name = (it.get('category') or '').strip()
            if not cat_name:
                continue
            cur = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
            if not cur:
                cur = IngredientCategory(
                    name=cat_name,
                    organization_id=None,
                    is_active=True,
                    is_global_category=True,
                    default_density=default_map.get(cat_name)
                )
                db.session.add(cur)
                db.session.flush()

        for it in items:
            name = (it.get('name') or '').strip()
            if not name:
                continue
            density = it.get('density_g_per_ml')
            aka = it.get('aka') or it.get('aliases') or []
            default_unit = it.get('default_unit') or None
            cat_name = (it.get('category') or '').strip()
            cur = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first() if cat_name else None

            existing = GlobalItem.query.filter_by(name=name, item_type='ingredient').first()
            if existing:
                existing.density = density
                existing.aka_names = aka
                existing.default_unit = default_unit
                existing.ingredient_category_id = cur.id if cur else None
            else:
                gi = GlobalItem(
                    name=name,
                    item_type='ingredient',
                    default_unit=default_unit,
                    density=density,
                    ingredient_category_id=(cur.id if cur else None),
                    aka_names=aka,
                )
                db.session.add(gi)

        db.session.commit()
        print("✅ Legacy density_reference.json processed")

