
import json
import os
import re
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.models import (
    db,
    GlobalItem,
    IngredientCategory,
    IngredientProfile,
    PhysicalForm,
    FunctionTag,
    ApplicationTag,
)


def _slugify(value: str) -> str:
    value = value or ''
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value or 'item'


def _unique_slug(model, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.session.query(model.id).filter_by(slug=slug).first():
        counter += 1
        slug = f"{base_slug}-{counter}"
    return slug


def _get_or_create_ingredient(ingredient_payload, fallback_name: str):
    name = (ingredient_payload or {}).get('name') or ingredient_payload.get('ingredient_name') if ingredient_payload else None
    if not name:
        name = fallback_name

    slug = ingredient_payload.get('slug') if ingredient_payload else None
    if slug:
        slug = _slugify(slug)
    else:
        slug = _slugify(name)

    ingredient = IngredientProfile.query.filter_by(slug=slug).first()
    if ingredient:
        # Update optional fields if provided
        if ingredient_payload:
            if ingredient_payload.get('aliases'):
                existing_aliases = set(ingredient.aliases or [])
                new_aliases = [alias for alias in ingredient_payload['aliases'] if alias not in existing_aliases]
                if new_aliases:
                    ingredient.aliases = list(existing_aliases.union(new_aliases))
            if ingredient_payload.get('inci_name'):
                ingredient.inci_name = ingredient_payload['inci_name']
            if ingredient_payload.get('cas_number'):
                ingredient.cas_number = ingredient_payload['cas_number']
            if ingredient_payload.get('description'):
                ingredient.description = ingredient_payload['description']
            if 'is_active_ingredient' in ingredient_payload:
                ingredient.is_active_ingredient = bool(ingredient_payload['is_active_ingredient'])
        return ingredient

    unique_slug = _unique_slug(IngredientProfile, slug)
    ingredient = IngredientProfile(
        name=name,
        slug=unique_slug,
        inci_name=(ingredient_payload or {}).get('inci_name'),
        cas_number=(ingredient_payload or {}).get('cas_number'),
        description=(ingredient_payload or {}).get('description'),
        aliases=(ingredient_payload or {}).get('aliases'),
        is_active_ingredient=bool((ingredient_payload or {}).get('is_active_ingredient', False)),
    )
    db.session.add(ingredient)
    db.session.flush()
    return ingredient


def _get_or_create_physical_form(name: str):
    normalized = (name or '').strip()
    if not normalized:
        normalized = 'Unspecified'
    slug = _slugify(normalized)
    physical_form = PhysicalForm.query.filter_by(slug=slug).first()
    if physical_form:
        return physical_form
    unique_slug = _unique_slug(PhysicalForm, slug)
    physical_form = PhysicalForm(name=normalized, slug=unique_slug, description=None)
    db.session.add(physical_form)
    db.session.flush()
    return physical_form


def _get_or_create_tag(model, name: str):
    normalized = (name or '').strip()
    if not normalized:
        return None
    slug = _slugify(normalized)
    tag = model.query.filter_by(slug=slug).first()
    if tag:
        if tag.name != normalized:
            tag.name = normalized
        return tag
    unique_slug = _unique_slug(model, slug)
    tag = model(name=normalized, slug=unique_slug)
    db.session.add(tag)
    db.session.flush()
    return tag


def _sync_item_tags(item, attribute_name: str, tag_model, tag_names):
    target_slugs = set()
    collection = getattr(item, attribute_name)

    for name in tag_names or []:
        tag = _get_or_create_tag(tag_model, name)
        if not tag:
            continue
        target_slugs.add(tag.slug)
        if tag not in collection:
            collection.append(tag)

    # Remove tags that are no longer present
    for existing in list(collection):
        if existing.slug not in target_slugs:
            collection.remove(existing)


def seed_ingredients_from_files(selected_files):
    """Seed ingredient categories first, then items"""
    if not selected_files:
        return 0, 0
    
    created_categories = 0
    created_items = 0
    
    base_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')
    
    for filename in selected_files:
        filepath = os.path.join(base_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                category_data = json.load(f)
        except Exception:
            continue
            
        cat_name = category_data.get('category_name', '').strip()
        if not cat_name:
            continue
        
        existing_cat = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
        if not existing_cat:
            new_cat = IngredientCategory(
                name=cat_name,
                description=category_data.get('description', ''),
                default_density=category_data.get('default_density'),
                is_global_category=True,
                organization_id=None,
                is_active=True
            )
            db.session.add(new_cat)
            db.session.flush()
            created_categories += 1
        
        category = existing_cat or new_cat
        
        for item_data in category_data.get('items', []):
            name = item_data.get('name', '').strip()
            if not name:
                continue

            ingredient_info = item_data.get('ingredient') or {}
            ingredient = _get_or_create_ingredient(ingredient_info, fallback_name=name)
            physical_form_name = item_data.get('physical_form')
            physical_form = _get_or_create_physical_form(physical_form_name)

            existing_item = GlobalItem.query.filter_by(
                name=name,
                item_type='ingredient'
            ).first()

            if existing_item:
                existing_item.ingredient = ingredient
                existing_item.physical_form = physical_form
                _sync_item_tags(existing_item, 'function_tags', FunctionTag, item_data.get('functions'))
                _sync_item_tags(existing_item, 'application_tags', ApplicationTag, item_data.get('applications'))
                continue

            density_value = item_data.get('density')
            if density_value is None:
                density_value = item_data.get('density_g_per_ml')

            aliases = item_data.get('aliases')
            if aliases is None:
                aliases = item_data.get('aka_names', item_data.get('aka', []))

            shelf_life = item_data.get('recommended_shelf_life_days')
            if shelf_life is None:
                shelf_life = item_data.get('shelf_life_days')

            new_item = GlobalItem(
                name=name,
                item_type='ingredient',
                ingredient=ingredient,
                physical_form=physical_form,
                density=density_value,
                aliases=aliases,
                default_unit=item_data.get('default_unit'),
                ingredient_category_id=category.id,
                default_is_perishable=item_data.get('perishable', False),
                recommended_shelf_life_days=shelf_life,
                recommended_usage_rate=item_data.get('recommended_usage_rate'),
                recommended_fragrance_load_pct=item_data.get('recommended_fragrance_load_pct'),
                is_active_ingredient=bool(
                    item_data.get('is_active_ingredient',
                                  item_data.get('is_active', False))
                ),
                inci_name=item_data.get('inci_name'),
                certifications=item_data.get('certifications'),
                saponification_value=item_data.get('saponification_value'),
                iodine_value=item_data.get('iodine_value'),
                melting_point_c=item_data.get('melting_point_c'),
                flash_point_c=item_data.get('flash_point_c'),
                ph_value=item_data.get('ph_value'),
                moisture_content_percent=item_data.get('moisture_content_percent'),
                comedogenic_rating=item_data.get('comedogenic_rating'),
                fatty_acid_profile=item_data.get('fatty_acid_profile'),
                protein_content_pct=item_data.get('protein_content_pct'),
                brewing_color_srm=item_data.get('brewing_color_srm'),
                brewing_potential_sg=item_data.get('brewing_potential_sg'),
                brewing_diastatic_power_lintner=item_data.get('brewing_diastatic_power_lintner'),
            )
            
            db.session.add(new_item)
            db.session.flush()

            _sync_item_tags(new_item, 'function_tags', FunctionTag, item_data.get('functions'))
            _sync_item_tags(new_item, 'application_tags', ApplicationTag, item_data.get('applications'))
            created_items += 1
        
        db.session.flush()
    
    return created_categories, created_items


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Get available ingredient files
        base_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')
        available_files = []
        if os.path.exists(base_dir):
            for filename in os.listdir(base_dir):
                if filename.endswith('.json') and not filename.startswith('.'):
                    available_files.append(filename)
        
        if not available_files:
            print("No ingredient JSON files found")
            sys.exit(1)
        
        print("Available ingredient files:")
        for i, filename in enumerate(available_files, 1):
            print(f"  {i}. {filename}")
        
        print("\nOptions:")
        print("1. Seed all files")
        print("2. Select specific files")
        
        choice = input("\nEnter your choice (1 or 2): ").strip()
        
        if choice == "1":
            selected_files = available_files
        elif choice == "2":
            selection = input("Enter file numbers (comma-separated): ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                selected_files = [available_files[i] for i in indices if 0 <= i < len(available_files)]
            except (ValueError, IndexError):
                print("Invalid selection")
                sys.exit(1)
        else:
            print("Invalid choice")
            sys.exit(1)
        
        categories_created, items_created = seed_ingredients_from_files(selected_files)
        
        try:
            db.session.commit()
            print(f"\n🎉 Ingredients Seeding Complete!")
            print(f"📊 Categories created: {categories_created}")
            print(f"📊 Items created: {items_created}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed during commit: {e}")
