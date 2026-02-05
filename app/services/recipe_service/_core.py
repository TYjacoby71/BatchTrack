"""Recipe core operations.

Synopsis:
Implements recipe CRUD with versioning, group assignment, and locks.

Glossary:
- Master: Primary recipe version in a group.
- Variation: Branch with its own version line.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import sqlalchemy as sa

from flask_login import current_user

from ...extensions import db
from ...models import InventoryItem, Recipe, RecipeIngredient, RecipeGroup, Batch
from ...models.recipe import RecipeConsumable
from ...services.event_emitter import EventEmitter
from ...utils.code_generator import generate_recipe_prefix
from ...services.lineage_service import generate_group_prefix, generate_variation_prefix
from ._constants import _UNSET
from ._helpers import (
    _derive_label_prefix,
    _extract_category_data_from_request,
    _normalize_status,
    _resolve_current_org_id,
)
from ._imports import _ensure_inventory_item_for_import
from ._lineage import _log_lineage_event
from ._marketplace import _apply_marketplace_settings
from ._origin import _build_org_origin_context, _resolve_is_sellable
from ._portioning import _apply_portioning_settings
from ._validation import validate_recipe_data
from ._current import apply_current_flag

logger = logging.getLogger(__name__)

# --- Derive variation name ---
# Purpose: Derive a variation display name.
def _derive_variation_name(name: str | None, parent_name: str | None) -> str | None:
    if not name:
        return None
    if parent_name:
        try:
            parent_lower = parent_name.strip().lower()
            name_lower = name.strip().lower()
            if name_lower.startswith(parent_lower):
                suffix = name.strip()[len(parent_name):].strip(" -:")
                if suffix:
                    return suffix
        except Exception:
            pass
    return name


# --- Next version number ---
# Purpose: Compute next version number for a branch.
def _next_version_number(
    recipe_group_id: int | None,
    *,
    is_master: bool,
    variation_name: str | None,
) -> int:
    if not recipe_group_id:
        return 1
    query = Recipe.query.filter(
        Recipe.recipe_group_id == recipe_group_id,
        Recipe.is_master.is_(is_master),
        Recipe.test_sequence.is_(None),
    )
    if not is_master:
        query = query.filter(Recipe.variation_name == variation_name)
    max_ver = query.with_entities(sa.func.max(Recipe.version_number)).scalar()
    return int(max_ver or 0) + 1


# --- Next test sequence ---
# Purpose: Compute next test sequence for a branch.
def _next_test_sequence(
    recipe_group_id: int | None,
    *,
    is_master: bool,
    variation_name: str | None,
) -> int:
    if not recipe_group_id:
        return 1
    query = Recipe.query.filter(
        Recipe.recipe_group_id == recipe_group_id,
        Recipe.is_master.is_(is_master),
        Recipe.test_sequence.isnot(None),
    )
    if not is_master:
        query = query.filter(Recipe.variation_name == variation_name)
    max_test = query.with_entities(sa.func.max(Recipe.test_sequence)).scalar()
    return int(max_test or 0) + 1


# --- Ensure recipe group ---
# Purpose: Ensure recipe group exists for a recipe.
def _ensure_recipe_group(
    *,
    recipe_org_id: int,
    group_name: str,
    group_prefix: str | None = None,
) -> RecipeGroup:
    prefix = group_prefix or generate_group_prefix(group_name, recipe_org_id)
    recipe_group = RecipeGroup(
        organization_id=recipe_org_id,
        name=group_name,
        prefix=prefix,
    )
    db.session.add(recipe_group)
    db.session.flush()
    return recipe_group


# --- Create recipe ---
# Purpose: Create a recipe with group/version metadata.
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
                 product_store_url: str | None = None,
                 cover_image_path: str | None = None,
                 cover_image_url: str | None = None,
                 skin_opt_in: bool | None = None,
                 remove_cover_image: bool = False,
                 is_sellable: bool | None = None,
                 recipe_group_id: int | None = None,
                 group_name: str | None = None,
                 group_prefix: str | None = None,
                 variation_name: str | None = None,
                 parent_master_id: int | None = None,
                 test_sequence: int | None = None,
                 is_test: bool | None = None,
                 version_number_override: int | None = None) -> Tuple[bool, Any]:
    """
    Create a new recipe with ingredients and UI fields.

    Args:
        name: Recipe name
        description: Recipe description
        instructions: Cooking instructions
        yield_amount: Expected yield quantity
        yield_unit: Unit for yield
        ingredients: List of ingredient dicts with item_id, quantity, unit
          parent_recipe_id: Parent recipe id for variations (legacy parent_id supported)
        allowed_containers: List of container IDs
        label_prefix: Label prefix for batches
        is_sellable: Optional override for marketplace resale eligibility

    Returns:
        Tuple of (success: bool, recipe_or_error: Recipe|str)
    """
    try:
        # Validate input data
        normalized_status = _normalize_status(status)
        is_test_flag = bool(is_test or test_sequence is not None)
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

        recipe_group = None
        if recipe_group_id:
            recipe_group = db.session.get(RecipeGroup, recipe_group_id)
        if not recipe_group and parent_recipe:
            recipe_group = parent_recipe.recipe_group if parent_recipe.recipe_group_id else None
            if not recipe_group:
                inherited_prefix = parent_recipe.label_prefix or None
                if inherited_prefix:
                    collision = RecipeGroup.query.filter_by(
                        organization_id=recipe_org_id,
                        prefix=inherited_prefix,
                    ).first()
                    if collision:
                        inherited_prefix = None
                recipe_group = _ensure_recipe_group(
                    recipe_org_id=recipe_org_id,
                    group_name=parent_recipe.name or (group_name or name),
                    group_prefix=inherited_prefix,
                )
                parent_recipe.recipe_group_id = recipe_group.id
        if not recipe_group:
            recipe_group = _ensure_recipe_group(
                recipe_org_id=recipe_org_id,
                group_name=group_name or name,
                group_prefix=group_prefix,
            )

        is_master = not bool(parent_recipe_id or parent_master_id)
        resolved_variation_name = None
        resolved_variation_prefix = None
        if not is_master:
            resolved_variation_name = variation_name or _derive_variation_name(
                name, parent_recipe.name if parent_recipe else None
            )
            existing_variation = None
            if recipe_group and resolved_variation_name:
                existing_variation = Recipe.query.filter(
                    Recipe.recipe_group_id == recipe_group.id,
                    Recipe.is_master.is_(False),
                    Recipe.variation_name == resolved_variation_name,
                ).order_by(Recipe.version_number.desc()).first()
            if existing_variation and existing_variation.variation_prefix:
                resolved_variation_prefix = existing_variation.variation_prefix
            else:
                resolved_variation_prefix = generate_variation_prefix(
                    resolved_variation_name or name,
                    recipe_group.id if recipe_group else None,
                )

        if version_number_override is not None:
            version_number = int(version_number_override)
        else:
            version_number = _next_version_number(
                recipe_group.id if recipe_group else None,
                is_master=is_master,
                variation_name=resolved_variation_name,
            )

        resolved_parent_master = None
        if not is_master:
            if parent_master_id:
                resolved_parent_master = db.session.get(Recipe, parent_master_id)
            if not resolved_parent_master and parent_recipe:
                resolved_parent_master = (
                    parent_recipe if parent_recipe.is_master else parent_recipe.parent_master
                )
            if not resolved_parent_master and recipe_group:
                resolved_parent_master = Recipe.query.filter(
                    Recipe.recipe_group_id == recipe_group.id,
                    Recipe.is_master.is_(True),
                ).order_by(Recipe.version_number.desc()).first()

        resolved_test_sequence = None
        if is_test_flag:
            resolved_test_sequence = test_sequence or _next_test_sequence(
                recipe_group.id if recipe_group else None,
                is_master=is_master,
                variation_name=resolved_variation_name,
            )

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
            recipe_group_id=recipe_group.id if recipe_group else None,
            is_master=is_master,
            variation_name=resolved_variation_name,
            variation_prefix=resolved_variation_prefix,
            version_number=version_number,
            parent_master_id=resolved_parent_master.id if resolved_parent_master else None,
            test_sequence=resolved_test_sequence,
            parent_recipe_id=parent_recipe_id,
            cloned_from_id=cloned_from_id,
            label_prefix=final_label_prefix,
            category_id=category_id,
            status=normalized_status
        )
        recipe.is_sellable = _resolve_is_sellable(
            explicit_flag=is_sellable,
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

        if normalized_status == "published" and not is_test_flag and not recipe.is_archived:
            apply_current_flag(recipe)
        else:
            recipe.is_current = False

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


# --- Update recipe ---
# Purpose: Update a recipe with lock/version safeguards.
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
                 product_store_url: str | None = None,
                 cover_image_path: Any = _UNSET,
                 cover_image_url: Any = _UNSET,
                 skin_opt_in: bool | None = None,
                 remove_cover_image: bool = False,
                 is_test: bool | None = None) -> Tuple[bool, Any]:
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
        if recipe.is_archived:
            return False, "Archived recipes cannot be modified"

        has_batches = Batch.query.filter_by(recipe_id=recipe_id).count()
        if recipe.status == 'published' and recipe.test_sequence is None:
            return False, "Published versions are locked. Create a test to make edits."
        if recipe.test_sequence is not None and has_batches > 0:
            return False, "Tests cannot be edited after running batches."

        target_status = _normalize_status(status if status is not None else recipe.status)
        allow_partial = target_status == 'draft'
        recipe.status = target_status

        if recipe.parent_recipe_id and recipe.is_master:
            recipe.is_master = False

        if recipe.recipe_group_id is None and recipe.organization_id:
            parent_candidate = recipe.parent
            if not parent_candidate and recipe.parent_recipe_id:
                parent_candidate = db.session.get(Recipe, recipe.parent_recipe_id)
            if parent_candidate and parent_candidate.recipe_group_id:
                recipe.recipe_group_id = parent_candidate.recipe_group_id
            else:
                inherited_prefix = getattr(parent_candidate, "label_prefix", None) or recipe.label_prefix
                if inherited_prefix:
                    collision = RecipeGroup.query.filter_by(
                        organization_id=recipe.organization_id,
                        prefix=inherited_prefix,
                    ).first()
                    if collision:
                        inherited_prefix = None
                recipe_group = _ensure_recipe_group(
                    recipe_org_id=recipe.organization_id,
                    group_name=(parent_candidate.name if parent_candidate else recipe.name),
                    group_prefix=inherited_prefix,
                )
                recipe.recipe_group_id = recipe_group.id
                if parent_candidate and not parent_candidate.recipe_group_id:
                    parent_candidate.recipe_group_id = recipe_group.id

        if not recipe.is_master:
            if not recipe.variation_name:
                recipe.variation_name = _derive_variation_name(
                    recipe.name, recipe.parent.name if recipe.parent else None
                )
            if not recipe.variation_prefix:
                recipe.variation_prefix = generate_variation_prefix(
                    recipe.variation_name or recipe.name,
                    recipe.recipe_group_id,
                )
            if recipe.parent_master_id is None:
                resolved_parent_master = recipe.parent if recipe.parent and recipe.parent.is_master else recipe.parent_master
                if not resolved_parent_master and recipe.recipe_group_id:
                    resolved_parent_master = Recipe.query.filter(
                        Recipe.recipe_group_id == recipe.recipe_group_id,
                        Recipe.is_master.is_(True),
                    ).order_by(Recipe.version_number.desc()).first()
                if resolved_parent_master:
                    recipe.parent_master_id = resolved_parent_master.id

        effective_is_test = is_test if is_test is not None else (recipe.test_sequence is not None)
        if effective_is_test:
            if recipe.test_sequence is None:
                recipe.test_sequence = _next_test_sequence(
                    recipe.recipe_group_id,
                    is_master=recipe.is_master,
                    variation_name=recipe.variation_name,
                )
        else:
            recipe.test_sequence = None

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

        if recipe.status == "published" and recipe.test_sequence is None and not recipe.is_archived:
            apply_current_flag(recipe)
        else:
            recipe.is_current = False

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



# --- Delete recipe ---
# Purpose: Delete a recipe and related rows.
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



# --- Fetch recipe details ---
# Purpose: Fetch a recipe with access checks.
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
                or recipe.status != "published"
                or recipe.test_sequence is not None
                or recipe.marketplace_blocked
            ):
                raise PermissionError("Recipe is not available for import")

        return recipe

    except Exception as e:
        logger.error(f"Error retrieving recipe {recipe_id}: {str(e)}")
        raise


# --- Duplicate recipe ---
# Purpose: Duplicate a recipe for legacy clone flow.
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
        template.product_store_url = original.product_store_url
        template.skin_opt_in = original.skin_opt_in
        template.cover_image_path = original.cover_image_path
        template.cover_image_url = original.cover_image_url
        template.is_sellable = bool(getattr(original, "is_sellable", True))
        if allow_cross_org or getattr(original, "org_origin_purchased", False):
            template.is_sellable = False
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