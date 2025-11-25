"""
Recipe Core Operations

Handles CRUD operations for recipes with proper service integration.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Tuple
from flask import current_app
from flask_login import current_user
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
from ...extensions import db
from ._validation import validate_recipe_data
from ...utils.code_generator import generate_recipe_prefix
from ...services.event_emitter import EventEmitter

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
                 shopify_product_url: str | None = None,
                 cover_image_path: str | None = None,
                 cover_image_url: str | None = None,
                 skin_opt_in: bool | None = None,
                 remove_cover_image: bool = False) -> Tuple[bool, Any]:
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
        final_label_prefix = label_prefix
        if not final_label_prefix:
            # Generate prefix from recipe name if not provided
            final_label_prefix = generate_recipe_prefix(name)
            
            # For variations, ensure unique prefix
            if parent_recipe_id:
                if parent_recipe and parent_recipe.label_prefix:
                    # Use parent prefix with variation suffix
                    base_prefix = parent_recipe.label_prefix
                    # Check for existing variations with same base prefix
                    existing_variations = Recipe.query.filter(
                        Recipe.parent_recipe_id == parent_recipe_id,
                        Recipe.label_prefix.like(f"{base_prefix}%")
                    ).count()
                    if existing_variations > 0:
                        final_label_prefix = f"{base_prefix}V{existing_variations + 1}"
                    else:
                        final_label_prefix = f"{base_prefix}V1"

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

        origin_context = _build_org_origin_context(
            target_org_id=recipe.organization_id,
            parent_recipe=parent_recipe,
            clone_source=clone_source,
        )
        pending_org_origin_recipe_id = origin_context.get('org_origin_recipe_id')
        recipe.org_origin_type = origin_context['org_origin_type']
        recipe.org_origin_source_org_id = origin_context['org_origin_source_org_id']
        recipe.org_origin_source_recipe_id = origin_context['org_origin_source_recipe_id']
        recipe.org_origin_purchased = origin_context['org_origin_purchased']

        # Set allowed containers
        if allowed_containers:
            recipe.allowed_containers = allowed_containers

        normalized_scope = _normalize_sharing_scope(sharing_scope)
        inferred_public = normalized_scope == 'public'
        if is_public is not None:
            inferred_public = bool(is_public)
            normalized_scope = 'public' if inferred_public else 'private'
        recipe.sharing_scope = normalized_scope
        recipe.is_public = inferred_public
        recipe.is_for_sale = bool(is_for_sale) if inferred_public else False
        recipe.sale_price = _normalize_sale_price(sale_price if recipe.is_for_sale else None)
        recipe.marketplace_status = marketplace_status or _default_marketplace_status(recipe.is_public)
        recipe.marketplace_notes = marketplace_notes
        recipe.public_description = public_description
        if product_group_id is not _UNSET:
            recipe.product_group_id = product_group_id
        recipe.shopify_product_url = (shopify_product_url or '').strip() or None
        if skin_opt_in is None:
            recipe.skin_opt_in = True
        else:
            recipe.skin_opt_in = bool(skin_opt_in)
        recipe.cover_image_path = cover_image_path
        recipe.cover_image_url = cover_image_url
        if remove_cover_image:
            recipe.cover_image_path = None
            recipe.cover_image_url = None

        # Portioning data validation and assignment
        if portioning_data and isinstance(portioning_data, dict):
            try:
                if portioning_data.get('is_portioned'):
                    try:
                        pc = int(portioning_data.get('portion_count') or 0)
                    except Exception:
                        pc = 0
                    if pc <= 0:
                        if allow_partial:
                            pc = None
                        else:
                            return False, {
                                'message': 'For portioned recipes, portion count must be provided.',
                                'error': 'For portioned recipes, portion count must be provided.',
                                'missing_fields': ['portion count']
                            }
                    recipe.portioning_data = portioning_data
                    # Also set discrete columns
                    recipe.is_portioned = True
                    recipe.portion_name = portioning_data.get('portion_name')
                    recipe.portion_count = pc
                    recipe.portion_unit_id = portioning_data.get('portion_unit_id')
            except Exception:
                pass

        # Handle discrete portioning parameters (if passed separately)
        if is_portioned is not None:
            recipe.is_portioned = is_portioned
        if portion_name is not None:
            recipe.portion_name = portion_name
        if portion_count is not None:
            recipe.portion_count = portion_count
        if portion_unit_id is not None:
            recipe.portion_unit_id = portion_unit_id

        scope_changed = False
        if sharing_scope is not None:
            normalized_scope = _normalize_sharing_scope(sharing_scope)
            if recipe.sharing_scope != normalized_scope:
                scope_changed = True
            recipe.sharing_scope = normalized_scope
            recipe.is_public = normalized_scope == 'public'
        if is_public is not None:
            normalized_scope = 'public' if is_public else 'private'
            if recipe.sharing_scope != normalized_scope:
                scope_changed = True
                recipe.sharing_scope = normalized_scope
            recipe.is_public = bool(is_public)

        if product_group_id is not _UNSET:
            recipe.product_group_id = product_group_id
        if shopify_product_url is not None:
            recipe.shopify_product_url = shopify_product_url.strip() or None
        if skin_opt_in is not None:
            recipe.skin_opt_in = bool(skin_opt_in)

        if is_for_sale is not None:
            recipe.is_for_sale = bool(is_for_sale) if recipe.is_public else False
        else:
            if not recipe.is_public:
                recipe.is_for_sale = False

        if sale_price is not None or not recipe.is_for_sale:
            recipe.sale_price = _normalize_sale_price(sale_price) if recipe.is_for_sale else None

        if marketplace_notes is not None:
            recipe.marketplace_notes = marketplace_notes
        if public_description is not None:
            recipe.public_description = public_description

        status_candidate = marketplace_status
        if status_candidate is None and scope_changed:
            status_candidate = _default_marketplace_status(recipe.is_public)
        if status_candidate is not None:
            recipe.marketplace_status = status_candidate

        if cover_image_path is not _UNSET:
            recipe.cover_image_path = cover_image_path
        if cover_image_url is not _UNSET:
            recipe.cover_image_url = cover_image_url
        if remove_cover_image:
            recipe.cover_image_path = None
            recipe.cover_image_url = None

        # Capture category-specific structured fields if present in portioning_data surrogate
        try:
            # Collect known category fields from request context if available
            from flask import request
            payload = request.form if request.form else None
            if payload and isinstance(payload, dict):
                cat_data = {}
                keys = [
                    # Soaps
                    'superfat_pct','lye_concentration_pct','lye_type','soap_superfat','soap_water_pct','soap_lye_type',
                    # Candles
                    'fragrance_load_pct','candle_fragrance_pct','candle_vessel_ml','vessel_fill_pct','candle_fill_pct',
                    # Cosmetics/Lotions
                    'cosm_preservative_pct','cosm_emulsifier_pct','oil_phase_pct','water_phase_pct','cool_down_phase_pct',
                    # Baking
                    'base_ingredient_id','moisture_loss_pct','derived_pre_dry_yield_g','derived_final_yield_g','baker_base_flour_g',
                    # Herbal
                    'herbal_ratio'
                ]
                for key in keys:
                    if key in payload and payload.get(key) not in (None, ''):
                        cat_data[key] = payload.get(key)
                # Normalize alias: candle_fill_pct -> vessel_fill_pct
                if 'candle_fill_pct' in cat_data and 'vessel_fill_pct' not in cat_data:
                    cat_data['vessel_fill_pct'] = cat_data['candle_fill_pct']
                if cat_data:
                    recipe.category_data = cat_data
        except Exception:
            pass

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
                 product_group_id: int | None = None,
                 shopify_product_url: str | None = None,
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
        # DEBUG: Log update_recipe parameters
        logger.info(f"=== UPDATE_RECIPE DEBUG ===")
        logger.info(f"recipe_id: {recipe_id}")
        logger.info(f"name: {name}")
        logger.info(f"yield_amount: {yield_amount} (type: {type(yield_amount)})")
        logger.info(f"yield_unit: {yield_unit}")
        logger.info(f"portioning_data: {portioning_data}")
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

        # Apply portioning data updates (both JSON and discrete columns)
        if portioning_data is not None:
            # Clear if toggle OFF
            if not portioning_data or not portioning_data.get('is_portioned'):
                recipe.portioning_data = None
                recipe.is_portioned = False
                recipe.portion_name = None
                recipe.portion_count = None
                recipe.portion_unit_id = None
            else:
                try:
                    pc = int(portioning_data.get('portion_count') or 0)
                except Exception:
                    pc = 0
                if pc <= 0:
                    if allow_partial:
                        pc = None
                    else:
                        return False, {
                            'message': 'For portioned recipes, portion count must be provided.',
                            'error': 'For portioned recipes, portion count must be provided.',
                            'missing_fields': ['portion count']
                        }
                recipe.portioning_data = portioning_data
                # Also update discrete columns
                recipe.is_portioned = True
                recipe.portion_name = portioning_data.get('portion_name')
                recipe.portion_count = pc
                recipe.portion_unit_id = portioning_data.get('portion_unit_id')

        # Handle discrete portioning parameters (if passed separately)
        if is_portioned is not None:
            recipe.is_portioned = is_portioned
        if portion_name is not None:
            recipe.portion_name = portion_name
        if portion_count is not None:
            recipe.portion_count = portion_count
        if portion_unit_id is not None:
            recipe.portion_unit_id = portion_unit_id

        # Update ingredients if provided
        if ingredients is not None:
            # DEBUG: Log validation parameters
            logger.info(f"=== VALIDATION CALL DEBUG ===")
            logger.info(f"Calling validate_recipe_data with:")
            logger.info(f"  name: {recipe.name}")
            logger.info(f"  ingredients count: {len(ingredients) if ingredients else 0}")
            logger.info(f"  yield_amount: {recipe.predicted_yield} (from existing recipe)")
            logger.info(f"  recipe_id: {recipe_id}")
            
            # Validate new ingredients
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

        # Update category-specific structured fields if posted
        try:
            from flask import request
            payload = request.form if request.form else None
            if payload and isinstance(payload, dict):
                cat_data = {}
                for key in ['soap_superfat', 'soap_water_pct', 'soap_lye_type',
                            'candle_fragrance_pct', 'candle_vessel_ml',
                            'cosm_preservative_pct', 'cosm_emulsifier_pct',
                            'baker_base_flour_g', 'herbal_ratio']:
                    if key in payload and payload.get(key) not in (None, ''):
                        cat_data[key] = payload.get(key)
                # If any category data provided, set it; if none provided, preserve existing
                if cat_data:
                    recipe.category_data = cat_data
        except Exception:
            pass

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


def get_recipe_details(recipe_id: int) -> Optional[Recipe]:
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
        
        recipe = db.session.query(Recipe).options(
            joinedload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.inventory_item),
            joinedload(Recipe.recipe_consumables).joinedload(RecipeConsumable.inventory_item)
        ).filter(Recipe.id == recipe_id).first()

        if not recipe:
            return None

        # Check organization access
        if current_user.organization_id and recipe.organization_id != current_user.organization_id:
            raise PermissionError("Access denied to recipe")

        return recipe

    except Exception as e:
        logger.error(f"Error retrieving recipe {recipe_id}: {str(e)}")
        raise


def duplicate_recipe(recipe_id: int) -> Tuple[bool, Any]:
    """
    Create a copy of an existing recipe.

    Args:
        recipe_id: Recipe to duplicate

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        original = get_recipe_details(recipe_id)
        if not original:
            return False, "Original recipe not found"

        # Extract ingredient data
        ingredients = [
            {
                'item_id': ri.inventory_item_id,
                'quantity': ri.quantity,
                'unit': ri.unit
            }
            for ri in original.recipe_ingredients
        ]

        # Extract consumable data
        consumables = [
            {
                'item_id': rc.inventory_item_id,
                'quantity': rc.quantity,
                'unit': rc.unit
            }
            for rc in original.recipe_consumables
        ]

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
        template.shopify_product_url = original.shopify_product_url
        template.skin_opt_in = original.skin_opt_in
        template.cover_image_path = original.cover_image_path
        template.cover_image_url = original.cover_image_url
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