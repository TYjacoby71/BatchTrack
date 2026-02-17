import json
import os
import re
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import create_app
from app.models import GlobalItem, IngredientCategory, db
from app.models.ingredient_reference import (
    ApplicationTag,
    FunctionTag,
    IngredientCategoryTag,
    IngredientDefinition,
    PhysicalForm,
)

_ingredient_cache = {}
_physical_form_cache = {}
_function_tag_cache = {}
_application_tag_cache = {}
_category_tag_cache = {}


def _resolve_seed_default_unit(
    category_name: str | None, item_name: str | None, current_unit: str | None
) -> str | None:
    """Heuristic to choose industry-standard default units for US-first seed data.

    Goal: avoid always defaulting to base SI units (e.g., grams) when the common
    purchasing/handling unit in the US is different (e.g., gallons for milk/water,
    pounds for waxes/powders). This only applies when the current unit is empty
    or is one of the common "base" defaults.
    """
    cat = (category_name or "").strip().lower()
    name = (item_name or "").strip().lower()
    unit = (current_unit or "").strip().lower() or None

    base_defaults = {None, "", "gram", "g", "milliliter", "ml"}
    if unit not in base_defaults:
        return current_unit

    # Explicit commodity heuristics first
    if "milk" in name:
        return "gallon"

    # Category-level heuristics (US-first where it matches typical handling)
    if "liquids (aqueous)" in cat or "aqueous solutions" in cat:
        return "gallon"

    if "waxes" in cat or " wax" in name:
        return "lb"

    if "flours" in cat or "starches" in cat or "powders" in cat:
        return "lb"

    # Keep base defaults for domains that commonly stay metric at craft scale
    # (actives/preservatives/colorants/etc.)
    return current_unit or "gram"


def _slugify(value: str) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    # Replace non-alphanumeric with hyphen
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or None


def parse_ph_range(ph_input):
    """Parses a pH input which can be a single value, a range 'X-Y', or None."""
    if ph_input is None:
        return None, None, None

    ph_input = str(ph_input).strip()

    if "-" in ph_input:
        try:
            ph_min_str, ph_max_str = ph_input.split("-", 1)
            ph_min = float(ph_min_str.strip())
            ph_max = float(ph_max_str.strip())
            # For a range, the displayed ph_value could be the average or simply the min
            ph_value = (ph_min + ph_max) / 2
            return ph_value, ph_min, ph_max
        except ValueError:
            # If splitting or conversion fails, treat it as a single value or invalid
            pass

    try:
        ph_value = float(ph_input)
        return ph_value, None, None
    except ValueError:
        # If it's not a range and not a float, return None for all
        return None, None, None


def _get_or_create_ingredient(payload: dict) -> IngredientDefinition:
    """Fetch or create an ingredient definition from the payload."""
    name = (payload.get("name") or "").strip()
    if not name:
        return None

    slug = payload.get("slug") or _slugify(name)
    cache_key = slug or name
    if cache_key in _ingredient_cache:
        return _ingredient_cache[cache_key]

    query = IngredientDefinition.query
    if slug:
        query = query.filter(
            (IngredientDefinition.slug == slug) | (IngredientDefinition.name == name)
        )
    else:
        query = query.filter(IngredientDefinition.name == name)

    ingredient = query.first()
    if ingredient:
        updated = False
        if payload.get("inci_name") and not ingredient.inci_name:
            ingredient.inci_name = payload["inci_name"]
            updated = True
        if payload.get("cas_number") and not ingredient.cas_number:
            ingredient.cas_number = payload["cas_number"]
            updated = True
        if payload.get("description") and not ingredient.description:
            ingredient.description = payload["description"]
            updated = True
        if slug and not ingredient.slug:
            ingredient.slug = slug
            updated = True
        if updated:
            db.session.add(ingredient)
    else:
        ingredient = IngredientDefinition(
            name=name,
            slug=slug,
            inci_name=payload.get("inci_name"),
            cas_number=payload.get("cas_number"),
            description=payload.get("description"),
            is_active=True,
        )
        db.session.add(ingredient)
        db.session.flush()

    _ingredient_cache[cache_key] = ingredient
    return ingredient


def _derive_ingredient_payload(item_data: dict) -> dict:
    """Derive ingredient payload when explicit ingredient block absent."""
    ingredient_payload = item_data.get("ingredient") or {}
    if ingredient_payload:
        return ingredient_payload

    name = item_data.get("ingredient_name") or item_data.get("name", "")
    # Remove parenthetical form indicators when deriving base ingredient name
    name = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    name = re.sub(r"\s{2,}", " ", name)
    return {
        "name": name,
        "inci_name": item_data.get("inci_name"),
    }


def _get_or_create_physical_form(form_name: str | None) -> PhysicalForm | None:
    if not form_name:
        return None
    form_name = form_name.strip()
    if not form_name:
        return None

    slug = _slugify(form_name)
    cache_key = slug or form_name
    if cache_key in _physical_form_cache:
        return _physical_form_cache[cache_key]

    query = PhysicalForm.query
    if slug:
        physical_form = query.filter(
            (PhysicalForm.slug == slug) | (PhysicalForm.name == form_name)
        ).first()
    else:
        physical_form = query.filter(PhysicalForm.name == form_name).first()

    if physical_form:
        if slug and not physical_form.slug:
            physical_form.slug = slug
            db.session.add(physical_form)
    else:
        physical_form = PhysicalForm(
            name=form_name,
            slug=slug,
            is_active=True,
        )
        db.session.add(physical_form)
        db.session.flush()

    _physical_form_cache[cache_key] = physical_form
    return physical_form


def _get_or_create_function_tag(tag_name: str | None) -> FunctionTag | None:
    if not tag_name:
        return None
    tag_name = tag_name.strip()
    if not tag_name:
        return None

    slug = _slugify(tag_name)
    cache_key = slug or tag_name
    if cache_key in _function_tag_cache:
        return _function_tag_cache[cache_key]

    query = FunctionTag.query
    if slug:
        tag = query.filter(
            (FunctionTag.slug == slug) | (FunctionTag.name == tag_name)
        ).first()
    else:
        tag = query.filter(FunctionTag.name == tag_name).first()

    if tag:
        if slug and not tag.slug:
            tag.slug = slug
            db.session.add(tag)
    else:
        tag = FunctionTag(
            name=tag_name,
            slug=slug,
            is_active=True,
        )
        db.session.add(tag)
        db.session.flush()

    _function_tag_cache[cache_key] = tag
    return tag


def _get_or_create_application_tag(tag_name: str | None) -> ApplicationTag | None:
    if not tag_name:
        return None
    tag_name = tag_name.strip()
    if not tag_name:
        return None

    slug = _slugify(tag_name)
    cache_key = slug or tag_name
    if cache_key in _application_tag_cache:
        return _application_tag_cache[cache_key]

    query = ApplicationTag.query
    if slug:
        tag = query.filter(
            (ApplicationTag.slug == slug) | (ApplicationTag.name == tag_name)
        ).first()
    else:
        tag = query.filter(ApplicationTag.name == tag_name).first()

    if tag:
        if slug and not tag.slug:
            tag.slug = slug
            db.session.add(tag)
    else:
        tag = ApplicationTag(
            name=tag_name,
            slug=slug,
            is_active=True,
        )
        db.session.add(tag)
        db.session.flush()

    _application_tag_cache[cache_key] = tag
    return tag


def _get_or_create_category_tag(tag_name: str | None) -> IngredientCategoryTag | None:
    if not tag_name:
        return None
    tag_name = tag_name.strip()
    if not tag_name:
        return None

    slug = _slugify(tag_name)
    cache_key = slug or tag_name
    if cache_key in _category_tag_cache:
        return _category_tag_cache[cache_key]

    query = IngredientCategoryTag.query
    if slug:
        tag = query.filter(
            (IngredientCategoryTag.slug == slug)
            | (IngredientCategoryTag.name == tag_name)
        ).first()
    else:
        tag = query.filter(IngredientCategoryTag.name == tag_name).first()

    if tag:
        if slug and not tag.slug:
            tag.slug = slug
            db.session.add(tag)
    else:
        tag = IngredientCategoryTag(
            name=tag_name,
            slug=slug,
            is_active=True,
        )
        db.session.add(tag)
        db.session.flush()

    _category_tag_cache[cache_key] = tag
    return tag


def _assign_tags(
    global_item: GlobalItem, item_data: dict, fallback_category_name: str | None = None
):
    """Attach function and application tags to a global item."""
    functions = item_data.get("functions") or []
    applications = item_data.get("applications") or []
    category_tags = item_data.get("category_tags") or []
    if fallback_category_name:
        if not category_tags:
            category_tags = [fallback_category_name]
        elif fallback_category_name not in category_tags:
            category_tags.append(fallback_category_name)

    global_item.functions = []
    for tag_name in functions:
        tag = _get_or_create_function_tag(tag_name)
        if tag:
            global_item.functions.append(tag)

    global_item.applications = []
    for tag_name in applications:
        tag = _get_or_create_application_tag(tag_name)
        if tag:
            global_item.applications.append(tag)

    resolved_category_tags = []
    for tag_name in category_tags:
        tag = _get_or_create_category_tag(tag_name)
        if tag:
            resolved_category_tags.append(tag)
    global_item.category_tags = resolved_category_tags


def seed_ingredients_from_files(selected_files):
    """Seed ingredient categories first, then items"""
    if not selected_files:
        return 0, 0

    created_categories = 0
    created_items = 0

    base_dir = os.path.join(
        os.path.dirname(__file__), "globallist", "ingredients", "categories"
    )

    for filename in selected_files:
        filepath = os.path.join(base_dir, filename)

        try:
            with open(filepath, "r") as f:
                category_data = json.load(f)
        except Exception:
            continue

        cat_name = category_data.get("category_name", "").strip()
        if not cat_name:
            continue

        existing_cat = IngredientCategory.query.filter_by(
            name=cat_name, organization_id=None
        ).first()
        if not existing_cat:
            new_cat = IngredientCategory(
                name=cat_name,
                description=category_data.get("description", ""),
                default_density=category_data.get("default_density"),
                is_global_category=True,
                organization_id=None,
                is_active=True,
            )
            db.session.add(new_cat)
            db.session.flush()
            created_categories += 1

        category = existing_cat or new_cat

        for item_data in category_data.get("items", []):
            name = item_data.get("name", "").strip()
            if not name:
                continue

            existing_item = GlobalItem.query.filter_by(
                name=name, item_type="ingredient"
            ).first()

            if existing_item:
                continue

            # Parse pH range if present
            ph_value, ph_min, ph_max = parse_ph_range(item_data.get("ph_value"))

            ingredient_payload = _derive_ingredient_payload(item_data)
            ingredient = _get_or_create_ingredient(ingredient_payload)
            physical_form = _get_or_create_physical_form(item_data.get("physical_form"))

            if existing_item:
                global_item = existing_item
                global_item.aliases = item_data.get("aliases", [])
                global_item.density = item_data.get(
                    "density", category_data.get("default_density")
                )
                seeded_unit = item_data.get("default_unit")
                global_item.default_unit = (
                    _resolve_seed_default_unit(category.name, name, seeded_unit)
                    or "gram"
                )
                global_item.recommended_fragrance_load_pct = item_data.get(
                    "recommended_fragrance_load_pct"
                )
                global_item.recommended_shelf_life_days = item_data.get(
                    "recommended_shelf_life_days"
                )
                global_item.inci_name = item_data.get("inci_name")
                global_item.certifications = item_data.get("certifications", [])
                global_item.is_active_ingredient = item_data.get(
                    "is_active_ingredient", False
                )
                global_item.saponification_value = item_data.get("saponification_value")
                global_item.iodine_value = item_data.get("iodine_value")
                global_item.melting_point_c = item_data.get("melting_point_c")
                global_item.flash_point_c = item_data.get("flash_point_c")
                global_item.ph_value = ph_value
                global_item.ph_min = ph_min
                global_item.ph_max = ph_max
                global_item.moisture_content_percent = item_data.get(
                    "moisture_content_percent"
                )
                global_item.comedogenic_rating = item_data.get("comedogenic_rating")
                global_item.fatty_acid_profile = item_data.get("fatty_acid_profile")
                global_item.protein_content_pct = item_data.get("protein_content_pct")
                global_item.brewing_color_srm = item_data.get("brewing_color_srm")
                global_item.brewing_potential_sg = item_data.get("brewing_potential_sg")
                global_item.brewing_diastatic_power_lintner = item_data.get(
                    "brewing_diastatic_power_lintner"
                )
                global_item.metadata_json = item_data.get("metadata_json", {})
            else:
                global_item = GlobalItem(
                    name=name,
                    item_type="ingredient",
                    aliases=item_data.get("aliases", []),
                    density=item_data.get(
                        "density", category_data.get("default_density")
                    ),
                    default_unit=_resolve_seed_default_unit(
                        category.name, name, item_data.get("default_unit")
                    )
                    or "gram",
                    recommended_fragrance_load_pct=item_data.get(
                        "recommended_fragrance_load_pct"
                    ),
                    recommended_shelf_life_days=item_data.get(
                        "recommended_shelf_life_days"
                    ),
                    inci_name=item_data.get("inci_name"),
                    certifications=item_data.get("certifications", []),
                    is_active_ingredient=item_data.get("is_active_ingredient", False),
                    saponification_value=item_data.get("saponification_value"),
                    iodine_value=item_data.get("iodine_value"),
                    melting_point_c=item_data.get("melting_point_c"),
                    flash_point_c=item_data.get("flash_point_c"),
                    ph_value=ph_value,
                    ph_min=ph_min,
                    ph_max=ph_max,
                    moisture_content_percent=item_data.get("moisture_content_percent"),
                    comedogenic_rating=item_data.get("comedogenic_rating"),
                    fatty_acid_profile=item_data.get("fatty_acid_profile"),
                    protein_content_pct=item_data.get("protein_content_pct"),
                    brewing_color_srm=item_data.get("brewing_color_srm"),
                    brewing_potential_sg=item_data.get("brewing_potential_sg"),
                    brewing_diastatic_power_lintner=item_data.get(
                        "brewing_diastatic_power_lintner"
                    ),
                    metadata_json=item_data.get("metadata_json", {}),
                )
                db.session.add(global_item)
                created_items += 1

            global_item.ingredient_category_id = category.id
            if ingredient:
                if getattr(ingredient, "ingredient_category_id", None) != category.id:
                    ingredient.ingredient_category_id = category.id
                    db.session.add(ingredient)
                global_item.ingredient = ingredient
            if physical_form:
                global_item.physical_form = physical_form

            _assign_tags(global_item, item_data, fallback_category_name=category.name)

    return created_categories, created_items


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        # Get available ingredient files
        base_dir = os.path.join(
            os.path.dirname(__file__), "globallist", "ingredients", "categories"
        )
        available_files = []
        if os.path.exists(base_dir):
            for filename in os.listdir(base_dir):
                if filename.endswith(".json") and not filename.startswith("."):
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
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                selected_files = [
                    available_files[i] for i in indices if 0 <= i < len(available_files)
                ]
            except (ValueError, IndexError):
                print("Invalid selection")
                sys.exit(1)
        else:
            print("Invalid choice")
            sys.exit(1)

        categories_created, items_created = seed_ingredients_from_files(selected_files)

        try:
            db.session.commit()
            print("\n🎉 Ingredients Seeding Complete!")
            print(f"📊 Categories created: {categories_created}")
            print(f"📊 Items created: {items_created}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed during commit: {e}")
