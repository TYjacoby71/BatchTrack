"""
Recipe Core Operations

Handles CRUD operations for recipes with proper service integration.
"""

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Tuple
from flask import current_app, session
from flask_login import current_user
from sqlalchemy import func


def _resolve_current_org_id() -> Optional[int]:
    """Best-effort helper to determine the organization for the active user."""
    try:
        if getattr(current_user, 'is_authenticated', False):
            if getattr(current_user, 'user_type', None) == 'developer':
                return session.get('dev_selected_org_id')
            return getattr(current_user, 'organization_id', None)
    except Exception:
        return None
    return None


from ...models import Recipe, RecipeIngredient, InventoryItem
from ...models.recipe import RecipeConsumable, RecipeLineage
from ...models.global_item import GlobalItem
from ...extensions import db
from ._validation import validate_recipe_data
from ...utils.code_generator import generate_recipe_prefix
from ...services.event_emitter import EventEmitter
from ..inventory_adjustment._creation_logic import create_inventory_item

logger = logging.getLogger(__name__)

_ALLOWED_RECIPE_STATUSES = {'draft', 'published'}
_UNSET = object()
_CENTS = Decimal("0.01")


def _normalize_sharing_scope(value: str | None) -> str:
    """Clamp sharing scope to supported values."""
    if not value:
        return 'private'
    normalized = str(value).strip().lower()
    if normalized in {'public', 'pub', 'shared'}:
        return 'public'
    return 'private'


def _default_marketplace_status(is_public: bool) -> str:
    return 'listed' if is_public else 'draft'


def _normalize_sale_price(value: Any) -> Optional[Decimal]:
    if value in (None, '', _UNSET):
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if price < 0:
        return None
    return price.quantize(_CENTS)


def _normalize_status(value: str | None) -> str:
    if not value:
        return 'published'
    normalized = str(value).strip().lower()
    return normalized if normalized in _ALLOWED_RECIPE_STATUSES else 'published'


def _get_batchtrack_org_id() -> int:
    try:
        return int(current_app.config.get('BATCHTRACK_ORG_ID', 1))
    except Exception:
        return 1


def _default_org_origin_type(org_id: Optional[int]) -> str:
    if org_id and org_id == _get_batchtrack_org_id():
        return 'batchtrack_native'
    return 'authored'


def _build_org_origin_context(
    target_org_id: Optional[int],
    parent_recipe: Optional[Recipe],
    clone_source: Optional[Recipe],
) -> Dict[str, Any]:
    context = {
        'org_origin_type': _default_org_origin_type(target_org_id),
        'org_origin_source_org_id': None,
        'org_origin_source_recipe_id': None,
        'org_origin_purchased': False,
        'org_origin_recipe_id': None,
    }

    if parent_recipe and parent_recipe.organization_id == target_org_id:
        context['org_origin_recipe_id'] = parent_recipe.org_origin_recipe_id or parent_recipe.id
        context['org_origin_type'] = parent_recipe.org_origin_type or context['org_origin_type']
        context['org_origin_source_org_id'] = parent_recipe.org_origin_source_org_id
        context['org_origin_source_recipe_id'] = parent_recipe.org_origin_source_recipe_id
        context['org_origin_purchased'] = parent_recipe.org_origin_purchased or False
        return context

    if clone_source and clone_source.organization_id == target_org_id:
        context['org_origin_recipe_id'] = clone_source.org_origin_recipe_id or clone_source.id
        context['org_origin_type'] = clone_source.org_origin_type or context['org_origin_type']
        context['org_origin_source_org_id'] = clone_source.org_origin_source_org_id
        context['org_origin_source_recipe_id'] = clone_source.org_origin_source_recipe_id
        context['org_origin_purchased'] = clone_source.org_origin_purchased or False
        return context

    source = parent_recipe or clone_source
    if source and source.organization_id and source.organization_id != target_org_id:
        context['org_origin_type'] = 'purchased'
        context['org_origin_purchased'] = True
        context['org_origin_source_org_id'] = source.organization_id
        context['org_origin_source_recipe_id'] = source.root_recipe_id or source.id

    return context


def _resolve_is_resellable(
    *,
    explicit_flag: bool | None,
    recipe_org_id: Optional[int],
    parent_recipe: Optional[Recipe],
    clone_source: Optional[Recipe],
    origin_context: Dict[str, Any],
) -> bool:
    """Determine whether a newly created recipe may be resold."""
    if explicit_flag is not None:
        return bool(explicit_flag)

    if origin_context.get('org_origin_purchased'):
        return False

    if (
        clone_source
        and clone_source.organization_id
        and recipe_org_id
        and clone_source.organization_id != recipe_org_id
    ):
        return False

    if clone_source and getattr(clone_source, 'is_resellable', True) is False:
        return False

    if parent_recipe and getattr(parent_recipe, 'is_resellable', True) is False:
        return False

    return True


def _resolve_import_name(fallback_name: Optional[str], global_item_id: Optional[int]) -> str:
    name = (fallback_name or "").strip()
    if name:
        return name
    if global_item_id:
        try:
            global_item = db.session.get(GlobalItem, int(global_item_id))
            if global_item and getattr(global_item, "name", None):
                return global_item.name
        except Exception:
            pass
    return "Imported Item"


_WORD_SANITIZE_RE = re.compile(r"[^a-z0-9\s]+")


def _singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith(("ses", "xes", "zes", "ches", "shes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _normalize_item_name_for_match(name: Optional[str]) -> str:
    if not name:
        return ""
    cleaned = _WORD_SANITIZE_RE.sub(" ", name.lower()).strip()
    if not cleaned:
        return ""
    tokens = [token for token in cleaned.split() if token]
    normalized_tokens = [_singularize_token(token) for token in tokens]
    return " ".join(normalized_tokens)


def _resolve_import_unit(
    fallback_unit: Optional[str],
    fallback_type: Optional[str],
    global_item: Optional[GlobalItem],
) -> str:
    if fallback_unit:
        return fallback_unit
    if global_item and getattr(global_item, "default_unit", None):
        return global_item.default_unit
    if (fallback_type or "").lower() == "container":
        return "count"
    return "gram"


def _ensure_inventory_item_for_import(
    *,
    organization_id: Optional[int],
    global_item_id: Optional[int],
    fallback_name: Optional[str],
    fallback_unit: Optional[str],
    fallback_type: Optional[str],
) -> Optional[int]:
    if not organization_id:
        return None

    if global_item_id:
        existing = (
            InventoryItem.query.filter(
                InventoryItem.organization_id == organization_id,
                InventoryItem.global_item_id == global_item_id,
            )
            .order_by(InventoryItem.id.asc())
            .first()
        )
        if existing:
            return existing.id

    global_item = None
    if global_item_id:
        try:
            global_item = db.session.get(GlobalItem, int(global_item_id))
        except Exception:
            global_item = None

    display_name = _resolve_import_name(
        fallback_name,
        global_item_id if global_item_id else None,
    )
    normalized_match_key = _normalize_item_name_for_match(display_name)
    normalized_type = fallback_type or (global_item.item_type if global_item else "ingredient")
    normalized_unit = _resolve_import_unit(fallback_unit, normalized_type, global_item)

    if not global_item_id and normalized_match_key:
        name_match = _match_inventory_item_by_normalized_name(
            organization_id,
            normalized_match_key,
            normalized_type,
        )
        if name_match:
            return name_match.id

    form_payload = {
        "name": display_name,
        "unit": normalized_unit,
        "type": normalized_type,
    }
    if global_item_id:
        form_payload["global_item_id"] = global_item_id

    success, message, item_id = create_inventory_item(
        form_payload,
        organization_id=organization_id,
        created_by=getattr(current_user, "id", None),
    )
    if not success:
        logger.warning("Unable to auto-create inventory item during import: %s", message)
        return None
    return item_id


def _match_inventory_item_by_normalized_name(
    organization_id: int,
    normalized_name: str,
    item_type: Optional[str],
) -> Optional[InventoryItem]:
    query = InventoryItem.query.filter(InventoryItem.organization_id == organization_id)
    if item_type:
        query = query.filter(InventoryItem.type == item_type)

    candidates = query.with_entities(InventoryItem.id, InventoryItem.name).all()
    for candidate_id, candidate_name in candidates:
        if _normalize_item_name_for_match(candidate_name) == normalized_name:
            return db.session.get(InventoryItem, candidate_id)
    return None


def _derive_label_prefix(
    name: str,
    requested_prefix: Optional[str],
    parent_recipe_id: Optional[int],
    parent_recipe: Optional[Recipe],
) -> str:
    if requested_prefix not in (None, ''):
        return requested_prefix

    final_prefix = generate_recipe_prefix(name)
    if parent_recipe_id and parent_recipe and parent_recipe.label_prefix:
        base_prefix = parent_recipe.label_prefix
        existing_variations = Recipe.query.filter(
            Recipe.parent_recipe_id == parent_recipe_id,
            Recipe.label_prefix.like(f"{base_prefix}%")
        ).count()
        suffix = existing_variations + 1
        return f"{base_prefix}V{suffix}"
    return final_prefix


def _clear_portioning(recipe: Recipe) -> None:
    recipe.portioning_data = None
    recipe.is_portioned = False
    recipe.portion_name = None
    recipe.portion_count = None
    recipe.portion_unit_id = None


def _apply_portioning_settings(
    recipe: Recipe,
    *,
    portioning_data: Optional[Dict[str, Any]],
    is_portioned: Optional[bool],
    portion_name: Optional[str],
    portion_count: Optional[int],
    portion_unit_id: Optional[int],
    allow_partial: bool,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    def _missing_count_error() -> Dict[str, Any]:
        return {
            'message': 'For portioned recipes, portion count must be provided.',
            'error': 'For portioned recipes, portion count must be provided.',
            'missing_fields': ['portion count']
        }

    if portioning_data is not None:
        wants_portioning = bool(portioning_data and portioning_data.get('is_portioned'))
        if wants_portioning:
            candidate = portioning_data.get('portion_count')
            try:
                resolved_count = int(candidate) if candidate is not None else 0
            except (TypeError, ValueError):
                resolved_count = 0

            if resolved_count <= 0:
                if allow_partial:
                    resolved_count = None
                else:
                    return False, _missing_count_error()

            recipe.portioning_data = dict(portioning_data)
            recipe.is_portioned = True
            recipe.portion_name = portioning_data.get('portion_name')
            recipe.portion_count = resolved_count
            recipe.portion_unit_id = portioning_data.get('portion_unit_id')
        else:
            _clear_portioning(recipe)

    if is_portioned is not None:
        recipe.is_portioned = bool(is_portioned)
        if not recipe.is_portioned:
            _clear_portioning(recipe)

    if portion_name is not None:
        recipe.portion_name = portion_name
    if portion_count is not None:
        recipe.portion_count = portion_count
    if portion_unit_id is not None:
        recipe.portion_unit_id = portion_unit_id

    if not recipe.is_portioned:
        _clear_portioning(recipe)

    return True, None


def _apply_marketplace_settings(
    recipe: Recipe,
    *,
    sharing_scope: Optional[str] = None,
    is_public: Optional[bool] = None,
    is_for_sale: Optional[bool] = None,
    sale_price: Any = None,
    marketplace_status: Optional[str] = None,
    marketplace_notes: Optional[str] = None,
    public_description: Optional[str] = None,
    product_group_id: Any = _UNSET,
    product_store_url: Optional[str] = None,
    skin_opt_in: Optional[bool] = None,
    cover_image_path: Any = _UNSET,
    cover_image_url: Any = _UNSET,
    remove_cover_image: bool = False,
) -> None:
    original_scope = recipe.sharing_scope or 'private'
    resolved_scope = original_scope
    if sharing_scope is not None:
        resolved_scope = _normalize_sharing_scope(sharing_scope)
    if is_public is not None:
        resolved_scope = 'public' if is_public else 'private'
    scope_changed = resolved_scope != (recipe.sharing_scope or 'private')
    recipe.sharing_scope = resolved_scope
    recipe.is_public = resolved_scope == 'public'

    if is_for_sale is not None:
        recipe.is_for_sale = bool(is_for_sale) and recipe.is_public
    elif not recipe.is_public:
        recipe.is_for_sale = False

    if sale_price is not None or not recipe.is_for_sale:
        recipe.sale_price = _normalize_sale_price(sale_price) if recipe.is_for_sale else None

    if getattr(recipe, "is_resellable", True) is False:
        recipe.is_for_sale = False
        recipe.sale_price = None

    if marketplace_status:
        recipe.marketplace_status = marketplace_status
    elif scope_changed or not recipe.marketplace_status:
        recipe.marketplace_status = _default_marketplace_status(recipe.is_public)

    if marketplace_notes is not None:
        recipe.marketplace_notes = marketplace_notes
    if public_description is not None:
        recipe.public_description = public_description

    if product_group_id is not _UNSET:
        recipe.product_group_id = product_group_id
    if product_store_url is not None:
        recipe.product_store_url = (product_store_url or '').strip() or None
    if skin_opt_in is not None:
        recipe.skin_opt_in = bool(skin_opt_in)

    if cover_image_path is not _UNSET:
        recipe.cover_image_path = cover_image_path
    if cover_image_url is not _UNSET:
        recipe.cover_image_url = cover_image_url
    if remove_cover_image:
        recipe.cover_image_path = None
        recipe.cover_image_url = None


def _extract_category_data_from_request() -> Optional[Dict[str, Any]]:
    try:
        from flask import request

        payload = request.form if request.form else None
        if not payload or not isinstance(payload, dict):
            return None
        keys = [
            'superfat_pct', 'lye_concentration_pct', 'lye_type', 'soap_superfat', 'soap_water_pct', 'soap_lye_type',
            'fragrance_load_pct', 'candle_fragrance_pct', 'candle_vessel_ml', 'vessel_fill_pct', 'candle_fill_pct',
            'cosm_preservative_pct', 'cosm_emulsifier_pct', 'oil_phase_pct', 'water_phase_pct', 'cool_down_phase_pct',
            'base_ingredient_id', 'moisture_loss_pct', 'derived_pre_dry_yield_g', 'derived_final_yield_g', 'baker_base_flour_g',
            'herbal_ratio'
        ]
        cat_data = {}
        for key in keys:
            value = payload.get(key)
            if value not in (None, ''):
                cat_data[key] = value
        if 'candle_fill_pct' in cat_data and 'vessel_fill_pct' not in cat_data:
            cat_data['vessel_fill_pct'] = cat_data['candle_fill_pct']
        return cat_data or None
    except Exception:
        return None

def create_recipe(name: str, description: str = "", instructions: str = "",
                 yield_amount: float = 0.0, yield_unit: str = "",
                 ingredients: List[Dict] = None, parent_id: int = None,
                 parent_recipe_id: int = None, cloned_from_id: int | None = None,
                 root_recipe_id: int | None = None,
                 allowed_containers: List[int] = None, label_prefix: str = "",
                 consumables: List[Dict] = None, category_id: int | None = None,
                 portioning_data: Dict | None = None,
                 is_portioned: bool = None, portion_name: str = None,
                 portion_count: int = None, portion_unit_id: int = None,
                 status: str = 'published',
                 sharing_scope: str = 'private',
                 is_public: bool | None = None,
                 is_for_sale: bool = False,
                 sale_price: Any = None,
                 marketplace_status: str | None = None,
                 marketplace_notes: str | None = None,
                 public_description: str | None = None,
                 product_group_id: Any = _UNSET,
                 product_store_url: str | None = None,
                 cover_image_path: str | None = None,
                 cover_image_url: str | None = None,
                 skin_opt_in: bool | None = None,
                 remove_cover_image: bool = False,
                 is_resellable: bool | None = None) -> Tuple[bool, Any]:
    """
    Create a new recipe with ingredients and UI fields.

    Args:
        name: Recipe name
        description: Recipe description
        instructions: Cooking instructions
        yield_amount: Expected yield quantity
        yield_unit: Unit for yield
        ingredients: List of ingredient dicts with item_id, quantity, unit
          parent_recipe_id: Parent recipe ID for variations (legacy parent_id supported)
        allowed_containers: List of container IDs
        label_prefix: Label prefix for batches
        is_resellable: Optional override for marketplace resale eligibility

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        # Validate input data
        normalized_status = _normalize_status(status)
        allow_partial = normalized_status == 'draft'

        current_org_id = _resolve_current_org_id()

        validation_result = validate_recipe_data(
            name=name,
            ingredients=ingredients or [],
            yield_amount=yield_amount,
            portioning_data=portioning_data,
            allow_partial=allow_partial,
            organization_id=current_org_id
        )

        if not validation_result['valid']:
            return False, validation_result

        parent_recipe_id = parent_recipe_id or parent_id
        parent_recipe = None
        clone_source = None
        try:
            if parent_recipe_id:
                parent_recipe = db.session.get(Recipe, parent_recipe_id)
            if cloned_from_id:
                clone_source = db.session.get(Recipe, cloned_from_id)
        except Exception:
            parent_recipe = parent_recipe or None
            clone_source = clone_source or None

        # Create recipe with proper label prefix
        final_label_prefix = _derive_label_prefix(name, label_prefix, parent_recipe_id, parent_recipe)

        # Derive predicted yield from portioning bulk if provided and > 0
        derived_yield = yield_amount
        derived_unit = yield_unit
        try:
            if portioning_data and portioning_data.get('is_portioned'):
                byq = float(portioning_data.get('bulk_yield_quantity') or 0)
                if byq > 0:
                    derived_yield = byq
                    # Map bulk_yield_unit_id -> unit string if available
                    buid = portioning_data.get('bulk_yield_unit_id')
                    if buid:
                        from ...models.unit import Unit
                        u = db.session.get(Unit, buid)
                        if u and getattr(u, 'name', None):
                            derived_unit = u.name
        except Exception:
            pass

        recipe_org_id = current_org_id if current_org_id else (1)

        origin_context = _build_org_origin_context(
            target_org_id=recipe_org_id,
            parent_recipe=parent_recipe,
            clone_source=clone_source,
        )
        pending_org_origin_recipe_id = origin_context.get('org_origin_recipe_id')

        recipe = Recipe(
            name=name,
            instructions=instructions,
            predicted_yield=derived_yield,
            predicted_yield_unit=derived_unit,
            organization_id=recipe_org_id,
            parent_recipe_id=parent_recipe_id,
            cloned_from_id=cloned_from_id,
            label_prefix=final_label_prefix,
            category_id=category_id,
            status=normalized_status
        )
        recipe.is_resellable = _resolve_is_resellable(
            explicit_flag=is_resellable,
            recipe_org_id=recipe.organization_id,
            parent_recipe=parent_recipe,
            clone_source=clone_source,
            origin_context=origin_context,
        )
        recipe.org_origin_type = origin_context['org_origin_type']
        recipe.org_origin_source_org_id = origin_context['org_origin_source_org_id']
        recipe.org_origin_source_recipe_id = origin_context['org_origin_source_recipe_id']
        recipe.org_origin_purchased = origin_context['org_origin_purchased']

        # Set allowed containers
        if allowed_containers:
            recipe.allowed_containers = allowed_containers

        if skin_opt_in is None:
            recipe.skin_opt_in = True

        _apply_marketplace_settings(
            recipe,
            sharing_scope=sharing_scope,
            is_public=is_public,
            is_for_sale=is_for_sale,
            sale_price=sale_price,
            marketplace_status=marketplace_status,
            marketplace_notes=marketplace_notes,
            public_description=public_description,
            product_group_id=product_group_id,
            product_store_url=product_store_url,
            skin_opt_in=skin_opt_in,
            cover_image_path=cover_image_path,
            cover_image_url=cover_image_url,
            remove_cover_image=remove_cover_image,
        )

        portion_ok, portion_error = _apply_portioning_settings(
            recipe,
            portioning_data=portioning_data,
            is_portioned=is_portioned,
            portion_name=portion_name,
            portion_count=portion_count,
            portion_unit_id=portion_unit_id,
            allow_partial=allow_partial,
        )
        if not portion_ok:
            db.session.rollback()
            return False, portion_error

        category_data_payload = _extract_category_data_from_request()
        if category_data_payload:
            recipe.category_data = category_data_payload

        # Determine lineage root
        inferred_root_id = root_recipe_id
        if not inferred_root_id:
            if parent_recipe:
                inferred_root_id = parent_recipe.root_recipe_id or parent_recipe.id
            elif clone_source:
                inferred_root_id = clone_source.root_recipe_id or clone_source.id

        if inferred_root_id:
            recipe.root_recipe_id = inferred_root_id

        db.session.add(recipe)
        db.session.flush()  # Get recipe ID

        if not recipe.root_recipe_id:
            recipe.root_recipe_id = recipe.id
            db.session.flush()

        recipe.org_origin_recipe_id = pending_org_origin_recipe_id or recipe.id
        db.session.flush()

        # Add ingredients
        for ingredient_data in ingredients or []:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                inventory_item_id=ingredient_data['item_id'],
                quantity=ingredient_data['quantity'],
                unit=ingredient_data['unit']
            )
            db.session.add(recipe_ingredient)

        # Add consumables
        for consumable in consumables or []:
            recipe_consumable = RecipeConsumable(
                recipe_id=recipe.id,
                inventory_item_id=consumable['item_id'],
                quantity=consumable['quantity'],
                unit=consumable['unit']
            )
            db.session.add(recipe_consumable)

        db.session.commit()

        # Log lineage metadata after commit to ensure recipe.id is available
        lineage_event = 'CREATE'
        lineage_source_id = None
        if parent_recipe_id:
            lineage_event = 'VARIATION'
            lineage_source_id = parent_recipe_id
        elif cloned_from_id:
            lineage_event = 'CLONE'
            lineage_source_id = cloned_from_id

        _log_lineage_event(recipe, lineage_event, lineage_source_id)
        logger.info(f"Created recipe {recipe.id}: {name}")

        # Emit recipe_created
        try:
            EventEmitter.emit(
                event_name='recipe_created',
                properties={'name': name, 'yield_amount': yield_amount, 'yield_unit': yield_unit},
                organization_id=recipe.organization_id,
                user_id=current_user.id,
                entity_type='recipe',
                entity_id=recipe.id
            )
        except Exception:
            pass

        return True, recipe

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating recipe: {e}")
        return False, str(e)


def update_recipe(recipe_id: int, name: str = None, description: str = None,
                 instructions: str = None, yield_amount: float = None,
                 yield_unit: str = None, ingredients: List[Dict] = None,
                 allowed_containers: List[int] = None, label_prefix: str = None,
                 consumables: List[Dict] = None, category_id: int | None = None,
                 portioning_data: Dict | None = None,
                 is_portioned: bool = None, portion_name: str = None,
                 portion_count: int = None, portion_unit_id: int = None,
                 status: str | None = None,
                 sharing_scope: str | None = None,
                 is_public: bool | None = None,
                 is_for_sale: bool | None = None,
                 sale_price: Any = None,
                 marketplace_status: str | None = None,
                 marketplace_notes: str | None = None,
                 public_description: str | None = None,
                 product_group_id: Any = _UNSET,
                 product_store_url: str | None = None,
                 cover_image_path: Any = _UNSET,
                 cover_image_url: Any = _UNSET,
                 skin_opt_in: bool | None = None,
                 remove_cover_image: bool = False) -> Tuple[bool, Any]:
    """
    Update an existing recipe.

    Args:
        recipe_id: Recipe to update
        name: New name (optional)
        description: New description (optional)
        instructions: New instructions (optional)
        yield_amount: New yield amount (optional)
        yield_unit: New yield unit (optional)
        ingredients: New ingredients list (optional)
        allowed_containers: New container list (optional)
        label_prefix: New label prefix (optional)

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return False, "Recipe not found"

        if recipe.is_locked:
            return False, "Recipe is locked and cannot be modified"

        target_status = _normalize_status(status if status is not None else recipe.status)
        allow_partial = target_status == 'draft'
        recipe.status = target_status

        # Update basic fields
        if name is not None:
            # Validate name uniqueness for updates
            validation_result = validate_recipe_data(
                name=name,
                recipe_id=recipe_id,
                allow_partial=True,
                organization_id=recipe.organization_id
            )
            if not validation_result['valid']:
                return False, validation_result
            recipe.name = name
        if instructions is not None:
            recipe.instructions = instructions
        if yield_amount is not None:
            recipe.predicted_yield = yield_amount
        if yield_unit is not None:
            recipe.predicted_yield_unit = yield_unit
        if label_prefix is not None:
            recipe.label_prefix = label_prefix
        if allowed_containers is not None:
            recipe.allowed_containers = allowed_containers
        if category_id is not None:
            recipe.category_id = category_id

        portion_ok, portion_error = _apply_portioning_settings(
            recipe,
            portioning_data=portioning_data,
            is_portioned=is_portioned,
            portion_name=portion_name,
            portion_count=portion_count,
            portion_unit_id=portion_unit_id,
            allow_partial=allow_partial,
        )
        if not portion_ok:
            db.session.rollback()
            return False, portion_error

        _apply_marketplace_settings(
            recipe,
            sharing_scope=sharing_scope,
            is_public=is_public,
            is_for_sale=is_for_sale,
            sale_price=sale_price,
            marketplace_status=marketplace_status,
            marketplace_notes=marketplace_notes,
            public_description=public_description,
            product_group_id=product_group_id,
            product_store_url=product_store_url,
            skin_opt_in=skin_opt_in,
            cover_image_path=cover_image_path,
            cover_image_url=cover_image_url,
            remove_cover_image=remove_cover_image,
        )

        # Update ingredients if provided
        if ingredients is not None:
            validation_result = validate_recipe_data(
                name=recipe.name,
                ingredients=ingredients,
                yield_amount=yield_amount if yield_amount is not None else recipe.predicted_yield,
                recipe_id=recipe_id,
                portioning_data=portioning_data,
                allow_partial=allow_partial,
                organization_id=recipe.organization_id
            )

            if not validation_result['valid']:
                return False, validation_result

            # Remove existing ingredients
            RecipeIngredient.query.filter_by(recipe_id=recipe_id).delete()

            # Add new ingredients
            for ingredient_data in ingredients:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    inventory_item_id=ingredient_data['item_id'],
                    quantity=ingredient_data['quantity'],
                    unit=ingredient_data['unit']
                )
                db.session.add(recipe_ingredient)

        # Update consumables if provided
        if consumables is not None:
            from ...models.recipe import RecipeConsumable
            RecipeConsumable.query.filter_by(recipe_id=recipe_id).delete()
            for item in consumables:
                db.session.add(RecipeConsumable(
                    recipe_id=recipe.id,
                    inventory_item_id=item['item_id'],
                    quantity=item['quantity'],
                    unit=item['unit']
                ))

        category_data_payload = _extract_category_data_from_request()
        if category_data_payload:
            recipe.category_data = category_data_payload

        db.session.commit()
        logger.info(f"Updated recipe {recipe_id}: {recipe.name}")

        # Emit recipe_updated
        try:
            EventEmitter.emit(
                event_name='recipe_updated',
                properties={'recipe_id': recipe_id},
                organization_id=recipe.organization_id,
                user_id=current_user.id,
                entity_type='recipe',
                entity_id=recipe.id
            )
        except Exception:
            pass

        return True, recipe

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating recipe {recipe_id}: {e}")
        return False, str(e)


def delete_recipe(recipe_id: int) -> Tuple[bool, str]:
    """
    Delete a recipe and its ingredients.

    Args:
        recipe_id: Recipe to delete

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return False, "Recipe not found"

        if recipe.is_locked:
            return False, "Recipe is locked and cannot be deleted"

        # Check for any batches (active or completed/cancelled)
        from ...models.batch import Batch
        any_batches = Batch.query.filter_by(recipe_id=recipe_id).count()

        if any_batches > 0:
            return False, "Cannot delete recipe that has been used in batches. Archive the recipe instead."

        recipe_name = recipe.name

        # Delete ingredients first (foreign key constraint)
        RecipeIngredient.query.filter_by(recipe_id=recipe_id).delete()

        # Delete recipe
        db.session.delete(recipe)
        db.session.commit()

        logger.info(f"Deleted recipe {recipe_id}: {recipe_name}")
        # Emit recipe_deleted
        try:
            EventEmitter.emit(
                event_name='recipe_deleted',
                properties={'name': recipe_name},
                organization_id=recipe.organization_id,
                user_id=current_user.id,
                entity_type='recipe',
                entity_id=recipe_id
            )
        except Exception:
            pass
        return True, f"Recipe '{recipe_name}' deleted successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting recipe {recipe_id}: {e}")
        return False, f"Error deleting recipe: {str(e)}"


def get_recipe_details(recipe_id: int, *, allow_cross_org: bool = False) -> Optional[Recipe]:
    """
    Get detailed recipe information with all relationships loaded.

    Args:
        recipe_id: ID of the recipe to retrieve

    Returns:
        Recipe object with relationships loaded, or None if not found

    Raises:
        ValueError: If recipe_id is invalid
        PermissionError: If user doesn't have access to recipe
    """
    if not recipe_id or recipe_id <= 0:
        raise ValueError("Invalid recipe ID")

    try:
        from sqlalchemy.orm import joinedload

        from ...models import RecipeIngredient, RecipeConsumable, InventoryItem

        recipe = (
            db.session.query(Recipe)
            .options(
                joinedload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.inventory_item),
                joinedload(Recipe.recipe_consumables).joinedload(RecipeConsumable.inventory_item),
            )
            .filter(Recipe.id == recipe_id)
            .first()
        )

        if not recipe:
            return None

        effective_org_id = _resolve_current_org_id()
        if not allow_cross_org and effective_org_id and recipe.organization_id != effective_org_id:
            raise PermissionError("Access denied to recipe")

        if allow_cross_org:
            if (
                not recipe.is_public
                or recipe.marketplace_status != "listed"
                or recipe.marketplace_blocked
            ):
                raise PermissionError("Recipe is not available for import")

        return recipe

    except Exception as e:
        logger.error(f"Error retrieving recipe {recipe_id}: {str(e)}")
        raise


def duplicate_recipe(
    recipe_id: int,
    *,
    allow_cross_org: bool = False,
    target_org_id: Optional[int] = None,
) -> Tuple[bool, Any]:
    """
    Create a copy of an existing recipe.

    Args:
        recipe_id: Recipe to duplicate

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        original = get_recipe_details(recipe_id, allow_cross_org=allow_cross_org)
        if not original:
            return False, "Original recipe not found"

        ingredient_globals: set[int] = set()
        consumable_globals: set[int] = set()
        for ri in original.recipe_ingredients:
            try:
                gi = getattr(getattr(ri, "inventory_item", None), "global_item_id", None)
                if gi:
                    ingredient_globals.add(int(gi))
            except Exception:
                continue
        for rc in original.recipe_consumables:
            try:
                gi = getattr(getattr(rc, "inventory_item", None), "global_item_id", None)
                if gi:
                    consumable_globals.add(int(gi))
            except Exception:
                continue

        target_org_for_mapping = target_org_id if allow_cross_org and target_org_id else original.organization_id
        global_match_map: dict[int, int] = {}
        if allow_cross_org and target_org_for_mapping and (ingredient_globals or consumable_globals):
            candidate_ids = list(ingredient_globals.union(consumable_globals))
            try:
                matches = (
                    InventoryItem.query.filter(
                        InventoryItem.organization_id == target_org_for_mapping,
                        InventoryItem.global_item_id.in_(candidate_ids),
                    ).all()
                )
                for item in matches:
                    if item.global_item_id and item.global_item_id not in global_match_map:
                        global_match_map[item.global_item_id] = item.id
            except Exception:
                logger.debug("Unable to pre-map inventory items for import; proceeding without matches.")

        ingredients: List[Dict[str, Any]] = []
        for ri in original.recipe_ingredients:
            inventory_item = getattr(ri, "inventory_item", None)
            global_id = getattr(inventory_item, "global_item_id", None)
            fallback_name = getattr(inventory_item, "name", None)
            fallback_unit = ri.unit or getattr(inventory_item, "unit", None)
            fallback_type = getattr(inventory_item, "type", None)

            target_item_id = ri.inventory_item_id
            if allow_cross_org:
                target_item_id = None
                if global_id and global_id in global_match_map:
                    target_item_id = global_match_map[global_id]
                else:
                    created_id = _ensure_inventory_item_for_import(
                        organization_id=target_org_for_mapping,
                        global_item_id=global_id,
                        fallback_name=fallback_name,
                        fallback_unit=fallback_unit,
                        fallback_type=fallback_type,
                    )
                    if created_id and global_id:
                        global_match_map[global_id] = created_id
                    target_item_id = created_id

            ingredients.append(
                {
                    "item_id": target_item_id,
                    "global_item_id": global_id,
                    "quantity": ri.quantity,
                    "unit": ri.unit,
                    "name": fallback_name,
                }
            )

        consumables: List[Dict[str, Any]] = []
        for rc in original.recipe_consumables:
            inventory_item = getattr(rc, "inventory_item", None)
            global_id = getattr(inventory_item, "global_item_id", None)
            fallback_name = getattr(inventory_item, "name", None)
            fallback_unit = rc.unit or getattr(inventory_item, "unit", None)
            fallback_type = getattr(inventory_item, "type", None)

            target_item_id = rc.inventory_item_id
            if allow_cross_org:
                target_item_id = None
                if global_id and global_id in global_match_map:
                    target_item_id = global_match_map[global_id]
                else:
                    created_id = _ensure_inventory_item_for_import(
                        organization_id=target_org_for_mapping,
                        global_item_id=global_id,
                        fallback_name=fallback_name,
                        fallback_unit=fallback_unit,
                        fallback_type=fallback_type or "consumable",
                    )
                    if created_id and global_id:
                        global_match_map[global_id] = created_id
                    target_item_id = created_id

            consumables.append(
                {
                    "item_id": target_item_id,
                    "global_item_id": global_id,
                    "quantity": rc.quantity,
                    "unit": rc.unit,
                    "name": fallback_name,
                }
            )

        clone_name = f"{original.name} (Copy)"
        clone_prefix = generate_recipe_prefix(clone_name)

        template = Recipe(
            name=clone_name,
            instructions=original.instructions,
            label_prefix=clone_prefix,
            predicted_yield=original.predicted_yield or 0.0,
            predicted_yield_unit=original.predicted_yield_unit or "",
            category_id=original.category_id,
            organization_id=original.organization_id,
            cloned_from_id=original.id,
            root_recipe_id=original.root_recipe_id or original.id
        )
        template.allowed_containers = list(original.allowed_containers or [])
        template.portioning_data = original.portioning_data.copy() if isinstance(original.portioning_data, dict) else original.portioning_data
        template.is_portioned = original.is_portioned
        template.portion_name = original.portion_name
        template.portion_count = original.portion_count
        template.portion_unit_id = original.portion_unit_id
        template.product_group_id = original.product_group_id
        template.product_store_url = original.product_store_url
        template.skin_opt_in = original.skin_opt_in
        template.cover_image_path = original.cover_image_path
        template.cover_image_url = original.cover_image_url
        template.is_resellable = bool(getattr(original, "is_resellable", True))
        if allow_cross_org or getattr(original, "org_origin_purchased", False):
            template.is_resellable = False
        template.sharing_scope = 'private'
        template.is_public = False
        template.is_for_sale = False
        template.sale_price = None
        template.marketplace_status = 'draft'

        return True, {
            'template': template,
            'ingredients': ingredients,
            'consumables': consumables,
            'cloned_from_id': original.id,
            'root_recipe_id': original.root_recipe_id or original.id
        }

    except Exception as e:
        logger.error(f"Error duplicating recipe {recipe_id}: {e}")
        return False, str(e)


def _log_lineage_event(recipe: Recipe, event_type: str, source_recipe_id: int | None = None, notes: str | None = None) -> None:
    """Persist a lineage audit row but never block recipe creation."""
    try:
        lineage = RecipeLineage(
            recipe_id=recipe.id,
            source_recipe_id=source_recipe_id,
            event_type=event_type,
            organization_id=recipe.organization_id,
            user_id=getattr(current_user, 'id', None),
            notes=notes
        )
        db.session.add(lineage)
    except Exception as exc:  # pragma: no cover - audit best-effort
        logger.debug(f"Unable to write recipe lineage event ({event_type}): {exc}")