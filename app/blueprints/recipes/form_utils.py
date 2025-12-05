from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Dict, Optional, Tuple

from flask import render_template
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import GlobalItem, InventoryItem, Recipe
from app.models.product_category import ProductCategory
from app.models.recipe_marketplace import RecipeProductGroup
from app.models.unit import Unit
from app.services.inventory_adjustment import create_inventory_item
from app.services.recipe_marketplace_service import RecipeMarketplaceService
from app.utils.cache_manager import app_cache
from app.utils.settings import is_feature_enabled
from app.utils.unit_utils import get_global_unit_list

logger = logging.getLogger(__name__)

_FORM_DATA_CACHE_TTL = int(os.getenv("RECIPE_FORM_CACHE_TTL", "60"))


def _recipe_form_cache_key(org_id: Optional[int]) -> str:
    return f"recipes:form_data:{org_id or 'global'}"


def _build_recipe_form_payload(org_id: Optional[int]) -> Dict[str, Any]:
    ingredients_query = InventoryItem.query.filter(InventoryItem.type == 'ingredient')
    if org_id:
        ingredients_query = ingredients_query.filter_by(organization_id=org_id)
    all_ingredients = ingredients_query.order_by(InventoryItem.name).all()

    consumables_query = InventoryItem.query.filter(InventoryItem.type == 'consumable')
    if org_id:
        consumables_query = consumables_query.filter_by(organization_id=org_id)
    all_consumables = consumables_query.order_by(InventoryItem.name).all()

    containers_query = InventoryItem.query.filter(InventoryItem.type == 'container')
    if org_id:
        containers_query = containers_query.filter_by(organization_id=org_id)
    all_containers = containers_query.order_by(InventoryItem.name).all()

    units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
    inventory_units = get_global_unit_list()

    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    # product_groups have been removed from the system
    product_groups = []

    return {
        'all_ingredients': all_ingredients,
        'all_consumables': all_consumables,
        'all_containers': all_containers,
        'units': units,
        'inventory_units': inventory_units,
        'product_categories': categories,
        'product_groups': product_groups,
    }


@dataclass
class RecipeFormSubmission:
    kwargs: Dict[str, Any]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def build_recipe_submission(
    form,
    files,
    *,
    defaults: Optional[Recipe] = None,
    existing: Optional[Recipe] = None,
) -> RecipeFormSubmission:
    ingredients = extract_ingredients_from_form(form)
    consumables = extract_consumables_from_form(form)
    allowed_containers = collect_allowed_containers(form)

    portion_payload, portion_fields = parse_portioning_from_form(form)
    category_id = safe_int(form.get('category_id'))

    fallback_yield = getattr(defaults, 'predicted_yield', None)
    if fallback_yield is None:
        fallback_yield = 0.0
    yield_amount = coerce_float(form.get('predicted_yield'), fallback=fallback_yield)
    fallback_unit = getattr(defaults, 'predicted_yield_unit', '') if defaults else ''
    yield_unit = form.get('predicted_yield_unit') or fallback_unit or ""

    marketplace_ok, marketplace_result = RecipeMarketplaceService.extract_submission(
        form, files, existing=existing
    )
    if not marketplace_ok:
        return RecipeFormSubmission({}, marketplace_result)

    kwargs: Dict[str, Any] = {
        'name': form.get('name'),
        'description': form.get('instructions'),
        'instructions': form.get('instructions'),
        'yield_amount': yield_amount,
        'yield_unit': yield_unit,
        'ingredients': ingredients,
        'consumables': consumables,
        'allowed_containers': allowed_containers,
        'label_prefix': form.get('label_prefix'),
        'category_id': category_id,
        'portioning_data': portion_payload,
        'is_portioned': portion_fields['is_portioned'],
        'portion_name': portion_fields['portion_name'],
        'portion_count': portion_fields['portion_count'],
        'portion_unit_id': portion_fields['portion_unit_id'],
    }
    kwargs.update(marketplace_result['marketplace'])
    kwargs.update(marketplace_result['cover'])

    return RecipeFormSubmission(kwargs)


def collect_allowed_containers(form) -> list[int]:
    containers: list[int] = []
    for raw in form.getlist('allowed_containers[]'):
        value = safe_int(raw)
        if value:
            containers.append(value)
    return containers


def parse_portioning_from_form(form) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    truthy = {'true', '1', 'yes', 'on'}
    flag = str(form.get('is_portioned') or '').strip().lower() in truthy
    default_fields = {
        'is_portioned': False,
        'portion_name': None,
        'portion_count': None,
        'portion_unit_id': None,
    }
    if not flag:
        return None, default_fields

    portion_name = (form.get('portion_name') or '').strip() or None
    portion_count = safe_int(form.get('portion_count'))
    portion_unit_id = ensure_portion_unit(portion_name)

    payload = {
        'is_portioned': True,
        'portion_name': portion_name,
        'portion_count': portion_count,
        'portion_unit_id': portion_unit_id,
    }
    return payload, payload.copy()


def ensure_portion_unit(portion_name: Optional[str]) -> Optional[int]:
    if not portion_name:
        return None

    try:
        existing = Unit.query.filter(Unit.name == portion_name).order_by(
            (Unit.organization_id == current_user.organization_id).desc()
        ).first()
    except Exception:
        existing = None

    if existing:
        return existing.id

    if not getattr(current_user, 'is_authenticated', False):
        return None

    try:
        unit = Unit(
            name=portion_name,
            unit_type='count',
            base_unit='count',
            conversion_factor=1.0,
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )
        db.session.add(unit)
        db.session.flush()
        return unit.id
    except Exception:
        db.session.rollback()
        return None


def coerce_float(value: Any, *, fallback: float = 0.0) -> float:
    if value in (None, ''):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def render_recipe_form(recipe=None, **context):
    form_data = get_recipe_form_data()
    payload = {**form_data, **context}
    return render_template('pages/recipes/recipe_form.html', recipe=recipe, **payload)


def recipe_from_form(form, base_recipe=None):
    recipe = Recipe()
    recipe.name = form.get('name') or (base_recipe.name if base_recipe else '')
    recipe.instructions = form.get('instructions') or (
        base_recipe.instructions if base_recipe else ''
    )
    recipe.label_prefix = form.get('label_prefix') or (
        base_recipe.label_prefix if base_recipe else ''
    )
    recipe.category_id = safe_int(form.get('category_id')) or (
        base_recipe.category_id if base_recipe else None
    )
    recipe.parent_recipe_id = (
        base_recipe.parent_recipe_id
        if base_recipe and getattr(base_recipe, 'parent_recipe_id', None)
        else None
    )

    product_store_url = form.get('product_store_url')
    if product_store_url is not None:
        recipe.product_store_url = product_store_url.strip() or None

    # product_group_id has been removed from the system

    try:
        if form.get('predicted_yield') not in (None, ''):
            recipe.predicted_yield = float(form.get('predicted_yield'))
        else:
            recipe.predicted_yield = (
                base_recipe.predicted_yield if base_recipe else None
            )
    except (TypeError, ValueError):
        recipe.predicted_yield = base_recipe.predicted_yield if base_recipe else None
    recipe.predicted_yield_unit = form.get('predicted_yield_unit') or (
        base_recipe.predicted_yield_unit if base_recipe else ''
    )

    recipe.allowed_containers = [
        int(identifier)
        for identifier in form.getlist('allowed_containers[]')
        if identifier
    ] or (
        list(base_recipe.allowed_containers)
        if base_recipe and base_recipe.allowed_containers
        else []
    )

    is_portioned = form.get('is_portioned') == 'true'
    recipe.is_portioned = is_portioned or (base_recipe.is_portioned if base_recipe else False)
    recipe.portion_name = form.get('portion_name') or (
        base_recipe.portion_name if base_recipe else None
    )
    try:
        if form.get('portion_count'):
            recipe.portion_count = int(form.get('portion_count'))
        else:
            recipe.portion_count = base_recipe.portion_count if base_recipe else None
    except (TypeError, ValueError):
        recipe.portion_count = base_recipe.portion_count if base_recipe else None
    recipe.portioning_data = (
        {
            'is_portioned': recipe.is_portioned,
            'portion_name': recipe.portion_name,
            'portion_count': recipe.portion_count,
        }
        if recipe.is_portioned
        else None
    )

    return recipe


def build_prefill_from_form(form):
    ingredient_ids = [safe_int(val) for val in form.getlist('ingredient_ids[]')]
    amounts = form.getlist('amounts[]')
    units = form.getlist('units[]')
    global_ids = [safe_int(val) for val in form.getlist('global_item_ids[]')]

    consumable_ids = [safe_int(val) for val in form.getlist('consumable_ids[]')]
    consumable_amounts = form.getlist('consumable_amounts[]')
    consumable_units = form.getlist('consumable_units[]')

    lookup_ids = [identifier for identifier in ingredient_ids + consumable_ids if identifier]
    name_lookup = lookup_inventory_names(lookup_ids)

    ingredient_rows = []
    for ing_id, gi_id, amt, unit in zip_longest(
        ingredient_ids, global_ids, amounts, units, fillvalue=None
    ):
        if not any([ing_id, gi_id, amt, unit]):
            continue
        ingredient_rows.append(
            {
                'inventory_item_id': ing_id,
                'global_item_id': gi_id,
                'quantity': amt,
                'unit': unit,
                'name': name_lookup.get(ing_id, ''),
            }
        )

    consumable_rows = []
    for cid, amt, unit in zip_longest(
        consumable_ids, consumable_amounts, consumable_units, fillvalue=None
    ):
        if not any([cid, amt, unit]):
            continue
        consumable_rows.append(
            {
                'inventory_item_id': cid,
                'quantity': amt,
                'unit': unit,
                'name': name_lookup.get(cid, ''),
            }
        )

    return ingredient_rows, consumable_rows


def serialize_prefill_rows(rows):
    ids = [row.get('item_id') for row in rows if row.get('item_id')]
    name_lookup = lookup_inventory_names(ids)
    serialized = []
    for row in rows:
        item_id = row.get('item_id')
        serialized.append(
            {
                'inventory_item_id': item_id,
                'global_item_id': row.get('global_item_id'),
                'quantity': row.get('quantity'),
                'unit': row.get('unit'),
                'name': row.get('name') or name_lookup.get(item_id, ''),
            }
        )
    return serialized


def serialize_assoc_rows(associations):
    serialized = []
    for assoc in associations:
        serialized.append(
            {
                'inventory_item_id': assoc.inventory_item_id,
                'quantity': assoc.quantity,
                'unit': assoc.unit,
                'name': assoc.inventory_item.name if assoc.inventory_item else '',
            }
        )
    return serialized


def lookup_inventory_names(item_ids):
    if not item_ids:
        return {}
    unique_ids = list({item_id for item_id in item_ids if item_id})
    if not unique_ids:
        return {}
    items = InventoryItem.query.filter(InventoryItem.id.in_(unique_ids)).all()
    return {item.id: item.name for item in items}


def safe_int(value):
    try:
        return int(value) if value not in (None, '', []) else None
    except (TypeError, ValueError):
        return None


def extract_ingredients_from_form(form):
    ingredients = []
    ingredient_ids = form.getlist('ingredient_ids[]')
    global_item_ids = form.getlist('global_item_ids[]')
    amounts = form.getlist('amounts[]')
    units = form.getlist('units[]')

    max_len = max(len(ingredient_ids), len(global_item_ids), len(amounts), len(units))
    ingredient_ids += [''] * (max_len - len(ingredient_ids))
    global_item_ids += [''] * (max_len - len(global_item_ids))
    amounts += [''] * (max_len - len(amounts))
    units += [''] * (max_len - len(units))

    for ing_id, gi_id, amt, unit in zip(ingredient_ids, global_item_ids, amounts, units):
        if not amt or not unit:
            continue

        try:
            quantity = float(str(amt).strip())
        except (ValueError, TypeError):
            logger.error("Invalid quantity provided for ingredient line: %s", amt)
            continue

        item_id = None
        if ing_id:
            try:
                item_id = int(ing_id)
            except (ValueError, TypeError):
                item_id = None

        if not item_id and gi_id:
            try:
                gi = db.session.get(GlobalItem, int(gi_id)) if gi_id else None
            except Exception:
                gi = None

            if gi:
                try:
                    existing = (
                        InventoryItem.query.filter_by(
                            organization_id=current_user.organization_id,
                            global_item_id=gi.id,
                            type=gi.item_type,
                        )
                        .order_by(InventoryItem.id.asc())
                        .first()
                    )
                except Exception:
                    existing = None

                if existing:
                    item_id = int(existing.id)
                else:
                    try:
                        name_match = (
                            InventoryItem.query.filter(
                                InventoryItem.organization_id == current_user.organization_id,
                                func.lower(InventoryItem.name)
                                == func.lower(db.literal(gi.name)),
                                InventoryItem.type == gi.item_type,
                            )
                            .order_by(InventoryItem.id.asc())
                            .first()
                        )
                    except Exception:
                        name_match = None

                    if name_match:
                        try:
                            name_match.global_item_id = gi.id
                            name_match.ownership = 'global'
                            db.session.flush()
                        except Exception:
                            db.session.rollback()
                        item_id = int(name_match.id)
                    else:
                        form_like = {
                            'name': gi.name,
                            'type': gi.item_type,
                            'unit': gi.default_unit or '',
                            'global_item_id': gi.id,
                        }

                        success, message, created_id = create_inventory_item(
                            form_data=form_like,
                            organization_id=current_user.organization_id,
                            created_by=current_user.id,
                        )
                        if not success:
                            logger.error(
                                "Failed to auto-create inventory for global item %s: %s",
                                gi.id,
                                message,
                            )
                        else:
                            item_id = int(created_id)
            else:
                logger.error("Global item not found for id %s", gi_id)

        if item_id:
            ingredients.append(
                {
                    'item_id': item_id,
                    'quantity': quantity,
                    'unit': (unit or '').strip(),
                }
            )

    return ingredients


def extract_consumables_from_form(form):
    consumables = []
    ids = form.getlist('consumable_ids[]')
    amounts = form.getlist('consumable_amounts[]')
    units = form.getlist('consumable_units[]')
    for item_id, amt, unit in zip(ids, amounts, units):
        if item_id and amt and unit:
            try:
                consumables.append(
                    {
                        'item_id': int(item_id),
                        'quantity': float(amt.strip()),
                        'unit': unit.strip(),
                    }
                )
            except (ValueError, TypeError) as exc:
                logger.error("Invalid consumable data: %s", exc)
                continue
    return consumables


def get_submission_status(form):
    mode = (form.get('save_mode') or '').strip().lower()
    return 'draft' if mode == 'draft' else 'published'


def parse_service_error(error):
    if isinstance(error, dict):
        message = error.get('error') or error.get('message') or 'An error occurred'
        missing_fields = error.get('missing_fields') or []
        return message, missing_fields
    return str(error), []


def build_draft_prompt(missing_fields, attempted_status, message):
    if missing_fields and attempted_status != 'draft':
        return {'missing_fields': missing_fields, 'message': message}
    return None


def get_recipe_form_data():
    org_id = getattr(current_user, 'organization_id', None)
    cache_key = _recipe_form_cache_key(org_id)
    cached = app_cache.get(cache_key)
    if cached is None:
        payload = _build_recipe_form_payload(org_id)
        try:
            app_cache.set(cache_key, payload, ttl=_FORM_DATA_CACHE_TTL)
        except Exception as exc:
            logger.debug("Unable to cache recipe form payload: %s", exc)
    else:
        payload = cached

    data = dict(payload)
    data['recipe_sharing_enabled'] = is_recipe_sharing_enabled()
    return data


def is_recipe_sharing_enabled():
    try:
        enabled = is_feature_enabled('FEATURE_RECIPE_SHARING_CONTROLS')
    except Exception:
        enabled = False
    if current_user.is_authenticated and getattr(current_user, 'user_type', '') == 'developer':
        return True
    return enabled


def create_variation_template(parent: Recipe) -> Recipe:
    variation_prefix = ""
    if parent.label_prefix:
        existing_variations = Recipe.query.filter_by(parent_recipe_id=parent.id).count()
        variation_prefix = f"{parent.label_prefix}V{existing_variations + 1}"

    template = Recipe(
        name=f"{parent.name} Variation",
        instructions=parent.instructions,
        label_prefix=variation_prefix,
        parent_recipe_id=parent.id,
        predicted_yield=parent.predicted_yield,
        predicted_yield_unit=parent.predicted_yield_unit,
        category_id=parent.category_id,
    )

    template.allowed_containers = list(parent.allowed_containers or [])
    if getattr(parent, 'org_origin_purchased', False):
        template.is_resellable = True
    else:
        template.is_resellable = getattr(parent, 'is_resellable', True)

    if parent.portioning_data:
        template.portioning_data = (
            parent.portioning_data.copy()
            if isinstance(parent.portioning_data, dict)
            else parent.portioning_data
        )
    template.is_portioned = parent.is_portioned
    template.portion_name = parent.portion_name
    template.portion_count = parent.portion_count
    template.portion_unit_id = parent.portion_unit_id

    if parent.category_data:
        template.category_data = (
            parent.category_data.copy()
            if isinstance(parent.category_data, dict)
            else parent.category_data
        )
    # product_group_id has been removed from the system
    template.skin_opt_in = parent.skin_opt_in
    template.sharing_scope = 'private'
    template.is_public = False
    template.is_for_sale = False

    template.product_store_url = parent.product_store_url
    template.recipe_collection_group_id = parent.recipe_collection_group_id

    return template