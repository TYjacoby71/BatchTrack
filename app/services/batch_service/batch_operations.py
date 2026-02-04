import logging
from datetime import date, datetime, timezone
from sqlalchemy import extract
from sqlalchemy.exc import IntegrityError
from flask_login import current_user

from app.models import db, Batch, Recipe, InventoryItem, BatchContainer, BatchIngredient, InventoryLot
from app.models.batch import BatchConsumable
from app import models
from app.models import ExtraBatchIngredient, ExtraBatchContainer, Product, ProductVariant
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.inventory_adjustment import process_inventory_adjustment
from app.utils.timezone_utils import TimezoneUtils
from app.utils.code_generator import generate_batch_label_code
from app.services.lineage_service import generate_lineage_id
from app.services.base_service import BaseService
from app.services.event_emitter import EventEmitter

logger = logging.getLogger(__name__)

class BatchOperationsService(BaseService):
    """Service for batch lifecycle operations: start, finish, cancel"""

    @classmethod

    def start_batch(cls, plan_snapshot: dict):
        """Start a new batch from an immutable plan snapshot. Rolls back on any failure."""

        try:
            # Trust the plan snapshot exclusively
            snap_recipe_id = int(plan_snapshot.get('recipe_id') or plan_snapshot.get('target_version_id'))
            snap_target_version_id = int(plan_snapshot.get('target_version_id') or snap_recipe_id)
            snap_scale = float(plan_snapshot.get('scale', 1.0))
            snap_batch_type = plan_snapshot.get('batch_type', 'ingredient')
            snap_notes = plan_snapshot.get('notes', '')
            forced_summary = plan_snapshot.get('forced_start_summary')
            if forced_summary:
                snap_notes = f"{snap_notes}\n{forced_summary}" if snap_notes else forced_summary
            snap_projected_yield = float(plan_snapshot.get('projected_yield') or 0.0)
            snap_projected_yield_unit = plan_snapshot.get('projected_yield_unit') or ''
            snap_portioning = plan_snapshot.get('portioning') or {}
            containers_data = plan_snapshot.get('containers') or []
            snap_lineage = plan_snapshot.get('lineage_snapshot')

            recipe = None

            containers_data = containers_data or []

            # Generate batch label via centralized generator (serialized per recipe row)
            label_code = None

            # Build portion snapshot from plan only
            portion_snap = None
            if snap_portioning and isinstance(snap_portioning, dict) and snap_portioning.get('is_portioned'):
                portion_snap = {
                    'is_portioned': True,
                    'portion_name': snap_portioning.get('portion_name'),
                    'portion_count': snap_portioning.get('portion_count'),
                    'portion_unit_id': snap_portioning.get('portion_unit_id')
                }

            # Ensure plan_snapshot is JSON-serializable. The API route should already pass a dict.
            serializable_plan_snapshot = None
            if plan_snapshot:
                if isinstance(plan_snapshot, dict):
                    serializable_plan_snapshot = plan_snapshot
                elif hasattr(plan_snapshot, 'to_dict'):
                    serializable_plan_snapshot = plan_snapshot.to_dict()
                else:
                    from dataclasses import asdict
                    try:
                        serializable_plan_snapshot = asdict(plan_snapshot)
                    except Exception:
                        serializable_plan_snapshot = plan_snapshot

            batch = None
            for attempt in range(3):
                recipe = Recipe.query.filter_by(id=snap_target_version_id).with_for_update().first()
                if not recipe:
                    return None, "Recipe not found"
                # Prefer plan-provided projected snapshot; otherwise derive from recipe at start time
                projected_yield = (
                    float(snap_projected_yield)
                    if snap_projected_yield is not None
                    else float(snap_scale) * float(recipe.predicted_yield or 0.0)
                )
                projected_yield_unit = (
                    snap_projected_yield_unit or recipe.predicted_yield_unit
                )
                if attempt == 0:
                    print(f"🔍 BATCH_SERVICE DEBUG: Starting batch from snapshot for recipe {recipe.name}")
                    # Create the batch
                    print(f"🔍 BATCH_SERVICE DEBUG: Creating batch with portioning snapshot: {portion_snap}")
                label_code = generate_batch_label_code(recipe)
                lineage_id = snap_lineage or generate_lineage_id(recipe)
                batch = Batch(
                    recipe_id=snap_recipe_id,
                    target_version_id=snap_target_version_id,
                    lineage_id=lineage_id,
                    label_code=label_code,
                    batch_type=snap_batch_type,
                    projected_yield=projected_yield,
                    projected_yield_unit=projected_yield_unit,
                    scale=snap_scale,
                    status='in_progress',
                    notes=snap_notes,
                    is_portioned=bool(portion_snap.get('is_portioned')) if portion_snap else False,
                    portion_name=portion_snap.get('portion_name') if portion_snap else None,
                    projected_portions=int(portion_snap.get('portion_count')) if portion_snap and portion_snap.get('portion_count') is not None else None,
                    portion_unit_id=portion_snap.get('portion_unit_id') if portion_snap else None,
                    plan_snapshot=serializable_plan_snapshot,
                    created_by=(getattr(current_user, 'id', None) or getattr(recipe, 'created_by', None) or 1),
                    organization_id=(getattr(current_user, 'organization_id', None) or getattr(recipe, 'organization_id', None) or 1),
                    started_at=TimezoneUtils.utc_now()
                )

                db.session.add(batch)
                try:
                    # Ensure batch is INSERTed so FK references in inventory history succeed
                    db.session.flush()
                    break
                except IntegrityError as exc:
                    db.session.rollback()
                    if attempt == 2:
                        logger.warning(
                            "Batch label collision after retries (recipe_id=%s, label=%s): %s",
                            snap_recipe_id,
                            label_code,
                            exc,
                        )
                        return None, ["Unable to allocate a unique batch label. Please retry."]
                    continue

            print(f"🔍 BATCH_SERVICE DEBUG: Batch object created with label: {label_code}")

            # Lock costing method for this batch at start based on organization setting
            try:
                if hasattr(batch, 'cost_method'):
                    org = getattr(current_user, 'organization', None)
                    method = (getattr(org, 'inventory_cost_method', None) or 'fifo') if org else 'fifo'
                    method = method if method in ('fifo', 'average') else 'fifo'
                    batch.cost_method = method
                    if hasattr(batch, 'cost_method_locked_at'):
                        batch.cost_method_locked_at = TimezoneUtils.utc_now()
            except Exception:
                try:
                    if hasattr(batch, 'cost_method'):
                        batch.cost_method = 'fifo'
                except Exception:
                    pass

            # Handle containers if required
            container_errors = cls._process_batch_containers(batch, containers_data, defer_commit=True)

            skip_ingredient_ids = set(plan_snapshot.get('skip_ingredient_ids', [])) if isinstance(plan_snapshot, dict) else set()
            skip_consumable_ids = set(plan_snapshot.get('skip_consumable_ids', [])) if isinstance(plan_snapshot, dict) else set()

            # Process ingredient deductions
            ingredient_errors = cls._process_batch_ingredients(
                batch,
                recipe,
                snap_scale,
                skip_ingredient_ids=skip_ingredient_ids,
                defer_commit=True
            )

            # Process consumable deductions
            consumable_errors = cls._process_batch_consumables(
                batch,
                recipe,
                snap_scale,
                skip_consumable_ids=skip_consumable_ids,
                defer_commit=True
            )

            # Combine all errors
            all_errors = container_errors + ingredient_errors + consumable_errors

            if all_errors:
                # Any deduction failure should abort the entire start
                db.session.rollback()
                return None, all_errors
            else:
                # All deductions validated; commit once atomically
                db.session.commit()

                # 🔍 FINAL SUCCESS DEBUG
                print(f"🔍 BATCH_SERVICE DEBUG: ✅ BATCH CREATED SUCCESSFULLY!")
                print(f"🔍 BATCH_SERVICE DEBUG: Final batch ID: {batch.id}")
                print(f"🔍 BATCH_SERVICE DEBUG: Final batch label: {batch.label_code}")
                # Verify batch was persisted
                fresh_batch = db.session.get(Batch, batch.id)
                if not fresh_batch:
                    print(f"🔍 BATCH_SERVICE DEBUG: ERROR - Could not fetch fresh batch from DB!")

                # Emit domain event for batch start (best-effort)
                try:
                    EventEmitter.emit(
                        event_name='batch_started',
                        properties={
                            'recipe_id': snap_recipe_id,
                            'scale': snap_scale,
                            'batch_type': snap_batch_type,
                            'projected_yield': projected_yield,
                            'projected_yield_unit': projected_yield_unit,
                            'label_code': batch.label_code,
                            'lineage_id': batch.lineage_id,
                            'portioning': portion_snap
                        },
                        organization_id=batch.organization_id,
                        user_id=batch.created_by,
                        entity_type='batch',
                        entity_id=batch.id
                    )
                except Exception:
                    pass

                return batch, []

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error starting batch: {str(e)}")
            return None, [str(e)]



    @classmethod
    def _process_batch_containers(cls, batch, containers_data, defer_commit=False):
        """Process container deductions for batch start"""
        errors = []
        try:
            for container in containers_data:
                container_id = container.get('id')
                quantity = container.get('quantity', 0)

                if container_id and quantity:
                    container_item = db.session.get(InventoryItem, container_id)
                    if container_item:
                        try:
                            # Handle container unit
                            container_unit = 'count' if not container_item.unit or container_item.unit == '' else container_item.unit

                            success, message = process_inventory_adjustment(
                                item_id=container_id,
                                quantity=-quantity,
                                change_type='batch',
                                unit=container_unit,
                                notes=f"Used in batch {batch.label_code}",
                                batch_id=batch.id,
                                created_by=current_user.id,
                                defer_commit=defer_commit
                            )

                            if success:
                                # Create BatchContainer record - cost via history aggregation (DRY)
                                try:
                                    from app.services.costing_engine import weighted_unit_cost_for_batch_item
                                    container_cost_snapshot = weighted_unit_cost_for_batch_item(container_item.id, batch.id)
                                except Exception:
                                    container_cost_snapshot = float(container_item.cost_per_unit or 0.0)

                                bc = BatchContainer(
                                    batch_id=batch.id,
                                    container_id=container_id,
                                    container_quantity=quantity,
                                    quantity_used=quantity,
                                    cost_each=container_cost_snapshot,
                                    organization_id=(getattr(current_user, 'organization_id', None) or 1)
                                )
                                db.session.add(bc)
                            else:
                                errors.append(message or f"Not enough {container_item.name} in stock.")
                        except Exception as e:
                            errors.append(f"Error adjusting inventory for {container_item.name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing batch containers: {str(e)}")
            errors.append(f"Error processing containers: {str(e)}")

        return errors

    @classmethod
    def _process_batch_ingredients(cls, batch, recipe, scale, skip_ingredient_ids=None, defer_commit=False):
        """Process ingredient deductions for batch start"""
        errors = []
        try:
            skip_ids = set(skip_ingredient_ids or [])
            for assoc in recipe.recipe_ingredients:
                ingredient = assoc.inventory_item
                if not ingredient:
                    continue

                if ingredient.id in skip_ids:
                    logger.info(f"Skipping deduction for {ingredient.name} (forced start with insufficient stock).")
                    continue

                required_amount = assoc.quantity * scale

                try:
                    conversion_result = ConversionEngine.convert_units(
                        required_amount,
                        assoc.unit,
                        ingredient.unit,
                        ingredient_id=ingredient.id,
                        density=ingredient.density or (ingredient.category.default_density if ingredient.category else None)
                    )
                    required_converted = conversion_result['converted_value']

                    # Use centralized inventory adjustment
                    success, message = process_inventory_adjustment(
                        item_id=ingredient.id,
                        change_type='batch',
                        quantity=required_converted,  # core handles sign for deductions
                        unit=ingredient.unit,
                        notes=f"Used in batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id,
                        defer_commit=True  # always defer commit during batch start
                    )

                    if not success:
                        errors.append(message or f"Not enough {ingredient.name} in stock.")
                        continue

                    # Create BatchIngredient record - cost via history aggregation (DRY)
                    try:
                        from app.services.costing_engine import weighted_unit_cost_for_batch_item
                        cost_per_unit_snapshot = weighted_unit_cost_for_batch_item(ingredient.id, batch.id)
                    except Exception:
                        cost_per_unit_snapshot = float(ingredient.cost_per_unit or 0.0)

                    batch_ingredient = BatchIngredient(
                        batch_id=batch.id,
                        inventory_item_id=ingredient.id,
                        quantity_used=required_converted,
                        unit=ingredient.unit,
                        cost_per_unit=cost_per_unit_snapshot,
                        organization_id=current_user.organization_id
                    )
                    db.session.add(batch_ingredient)

                except ValueError as e:
                    errors.append(f"Error converting units for {ingredient.name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing batch ingredients: {str(e)}")
            errors.append(f"Error processing ingredients: {str(e)}")

        return errors

    @classmethod
    def _process_batch_consumables(cls, batch, recipe, scale, skip_consumable_ids=None, defer_commit=False):
        """Process consumable deductions and snapshot for batch start"""
        errors = []
        try:
            # If recipe has no consumables relationship, skip gracefully
            consumables = getattr(recipe, 'recipe_consumables', []) or []
            skip_ids = set(skip_consumable_ids or [])
            for assoc in consumables:
                item = assoc.inventory_item
                if not item:
                    continue

                if item.id in skip_ids:
                    logger.info(f"Skipping consumable deduction for {item.name} (forced start with insufficient stock).")
                    continue

                required_amount = assoc.quantity * scale

                try:
                    # Align units to inventory unit
                    from app.services.unit_conversion import ConversionEngine
                    conversion_result = ConversionEngine.convert_units(
                        required_amount,
                        assoc.unit,
                        item.unit,
                        ingredient_id=item.id,
                        density=item.density or (item.category.default_density if item.category else None)
                    )
                    required_converted = conversion_result['converted_value']

                    success, message = process_inventory_adjustment(
                        item_id=item.id,
                        change_type='batch',
                        quantity=required_converted,  # core handles sign for deductions
                        unit=item.unit,
                        notes=f"Consumable used in batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id,
                        defer_commit=True
                    )

                    if not success:
                        errors.append(message or f"Not enough {item.name} in stock (consumable).")
                        continue

                    # Snapshot consumable cost via history aggregation (DRY)
                    try:
                        from app.services.costing_engine import weighted_unit_cost_for_batch_item
                        consumable_cost_snapshot = weighted_unit_cost_for_batch_item(item.id, batch.id)
                    except Exception:
                        consumable_cost_snapshot = float(item.cost_per_unit or 0.0)

                    snap = BatchConsumable(
                        batch_id=batch.id,
                        inventory_item_id=item.id,
                        quantity_used=required_converted,
                        unit=item.unit,
                        cost_per_unit=consumable_cost_snapshot,
                        organization_id=current_user.organization_id
                    )
                    db.session.add(snap)

                except ValueError as e:
                    errors.append(f"Error converting units for {item.name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing batch consumables: {str(e)}")
            errors.append(f"Error processing consumables: {str(e)}")

        return errors

    @classmethod
    def cancel_batch(cls, batch_id):
        """Cancel a batch and restore inventory"""
        try:
            from app.services.inventory_adjustment import validate_inventory_fifo_sync

            batch = Batch.scoped().filter_by(id=batch_id).first()
            if not batch:
                return False, "Batch not found"

            # Validate access
            if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
                return False, "Permission denied"

            if batch.status != 'in_progress':
                return False, "Only in-progress batches can be cancelled"

            # Get all items to restore
            batch_ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
            batch_containers = BatchContainer.query.filter_by(batch_id=batch.id).all()
            extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch.id).all()
            extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch.id).all()
            from app.models.batch import BatchConsumable, ExtraBatchConsumable
            batch_consumables = BatchConsumable.query.filter_by(batch_id=batch.id).all()
            extra_consumables = ExtraBatchConsumable.query.filter_by(batch_id=batch.id).all()

            # Pre-validate FIFO sync for all ingredients
            for batch_ingredient in batch_ingredients:
                is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(batch_ingredient.inventory_item_id)
                if not is_valid:
                    return False, f'Inventory sync error for {batch_ingredient.inventory_item.name}: {error_msg}'

            for extra_ingredient in extra_ingredients:
                is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(extra_ingredient.inventory_item_id)
                if not is_valid:
                    return False, f'Inventory sync error for {extra_ingredient.inventory_item.name}: {error_msg}'

            # Restore all inventory
            restoration_summary = []

            # Restore batch ingredients
            for batch_ing in batch_ingredients:
                ingredient = batch_ing.inventory_item
                if ingredient:
                    process_inventory_adjustment(
                        item_id=ingredient.id,
                        quantity=batch_ing.quantity_used,
                        change_type='refunded',
                        unit=batch_ing.unit,
                        notes=f"Ingredient refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{batch_ing.quantity_used} {batch_ing.unit} of {ingredient.name}")

            # Restore extra ingredients
            for extra_ing in extra_ingredients:
                ingredient = extra_ing.inventory_item
                if ingredient:
                    process_inventory_adjustment(
                        item_id=ingredient.id,
                        quantity=extra_ing.quantity_used,
                        change_type='refunded',
                        unit=extra_ing.unit,
                        notes=f"Extra ingredient refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{extra_ing.quantity_used} {extra_ing.unit} of {ingredient.name}")

            # Restore containers
            for batch_container in batch_containers:
                container = batch_container.inventory_item
                if container:
                    process_inventory_adjustment(
                        item_id=container.id,
                        quantity=batch_container.quantity_used,
                        change_type='refunded',
                        unit=batch_container.unit,
                        notes=f"Container refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{batch_container.quantity_used} {batch_container.unit} of {container.container_display_name}")

            # Restore extra containers
            for extra_container in extra_containers:
                container = extra_container.inventory_item
                if container:
                    process_inventory_adjustment(
                        item_id=container.id,
                        quantity=extra_container.quantity_used,
                        change_type='refunded',
                        unit=extra_container.unit,
                        notes=f"Extra container refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{extra_container.quantity_used} {extra_container.unit} of {container.container_display_name}")

            # Restore consumables
            for cons in batch_consumables:
                item = cons.inventory_item
                if item:
                    process_inventory_adjustment(
                        item_id=item.id,
                        quantity=cons.quantity_used,
                        change_type='refunded',
                        unit=cons.unit,
                        notes=f"Consumable refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{cons.quantity_used} {cons.unit} of {item.name}")

            # Restore extra consumables
            for extra_cons in extra_consumables:
                item = extra_cons.inventory_item
                if item:
                    process_inventory_adjustment(
                        item_id=item.id,
                        quantity=extra_cons.quantity_used,
                        change_type='refunded',
                        unit=extra_cons.unit,
                        notes=f"Extra consumable refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{extra_cons.quantity_used} {extra_cons.unit} of {item.name}")

            # Update batch status
            batch.status = 'cancelled'
            batch.cancelled_at = datetime.now(timezone.utc)
            db.session.commit()

            # Emit domain event (best-effort)
            try:
                EventEmitter.emit(
                    event_name='batch_cancelled',
                    properties={
                        'label_code': batch.label_code,
                        'restoration_summary': restoration_summary
                    },
                    organization_id=batch.organization_id,
                    user_id=batch.created_by,
                    entity_type='batch',
                    entity_id=batch.id
                )
            except Exception:
                pass

            return True, restoration_summary

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cancelling batch: {str(e)}")
            return False, str(e)

    @classmethod
    def complete_batch(cls, batch_id, form_data):
        """Complete a batch and create final products/ingredients"""
        try:
            # Import here to avoid circular imports
            from app.blueprints.batches.finish_batch import _complete_batch_internal

            org_id = getattr(current_user, 'organization_id', None)
            query = Batch.query.filter_by(
                id=batch_id,
                status='in_progress'
            )
            if org_id:
                query = query.filter_by(organization_id=org_id)
            batch = query.first()

            if not batch:
                return False, 'Batch not found or already completed'

            # Delegate to internal finish batch logic
            # This maintains the existing complex logic while keeping it out of routes
            success, message = _complete_batch_internal(batch_id, form_data)

            if success:
                try:
                    refreshed = db.session.get(Batch, batch_id)
                    # Mirror final_portions into batch for reporting if provided
                    try:
                        if refreshed and form_data.get('final_portions'):
                            val = int(form_data.get('final_portions'))
                            if val > 0:
                                refreshed.final_portions = val
                                db.session.commit()
                    except Exception:
                        pass
                    # Compute containment efficiency if BatchStats exists
                    from app.models.statistics import BatchStats as _BatchStats
                    stats = _BatchStats.query.filter_by(batch_id=batch_id).first()
                    containment_efficiency = getattr(stats, 'actual_fill_efficiency', None) if stats else None
                    # Compute accuracy (projected vs final yield)
                    accuracy_pct = None
                    if refreshed and refreshed.projected_yield and refreshed.final_quantity:
                        try:
                            if float(refreshed.projected_yield) > 0:
                                accuracy_pct = ((float(refreshed.final_quantity) - float(refreshed.projected_yield)) / float(refreshed.projected_yield)) * 100.0
                        except Exception:
                            accuracy_pct = None
                    # Compute overall freshness for event payload
                    try:
                        from app.services.freshness_service import FreshnessService
                        freshness_summary = FreshnessService.compute_batch_freshness(refreshed)
                        overall_freshness = getattr(freshness_summary, 'overall_freshness_percent', None)
                    except Exception:
                        overall_freshness = None
                    EventEmitter.emit(
                        event_name='batch_completed',
                        properties={
                            'label_code': refreshed.label_code,
                            'final_quantity': refreshed.final_quantity,
                            'output_unit': refreshed.output_unit,
                            'completed_at': (refreshed.completed_at.isoformat() if refreshed.completed_at else None),
                            'containment_efficiency': containment_efficiency,
                            'yield_accuracy_variance_pct': accuracy_pct,
                            'overall_freshness_percent': overall_freshness
                        },
                        organization_id=refreshed.organization_id,
                        user_id=refreshed.created_by,
                        entity_type='batch',
                        entity_id=refreshed.id
                    )
                except Exception:
                    pass

            return success, message

        except Exception as e:
            logger.error(f"Error completing batch: {str(e)}")
            return False, str(e)

    @classmethod
    def fail_batch(cls, batch_id, reason: str | None = None):
        """Mark an in-progress batch as failed. Does not attempt inventory restoration.

        Sets status to 'failed', clears in-progress state, and timestamps failure.
        """
        try:
            batch = Batch.query.filter_by(
                id=batch_id,
                organization_id=current_user.organization_id
            ).first()

            if not batch:
                return False, "Batch not found"

            if batch.status != 'in_progress':
                return False, "Only in-progress batches can be marked as failed"

            batch.status = 'failed'
            batch.failed_at = TimezoneUtils.utc_now()
            if reason:
                # Preserve any prior reason content by appending
                batch.status_reason = (batch.status_reason + "\n" if batch.status_reason else "") + str(reason)

            db.session.commit()

            # Emit domain event (best-effort)
            try:
                EventEmitter.emit(
                    event_name='batch_failed',
                    properties={
                        'label_code': batch.label_code,
                        'reason': reason
                    },
                    organization_id=batch.organization_id,
                    user_id=batch.created_by,
                    entity_type='batch',
                    entity_id=batch.id
                )
            except Exception:
                pass

            return True, f"Batch {batch.label_code} marked as failed"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error failing batch: {str(e)}")
            return False, str(e)

    @classmethod
    def add_extra_items_to_batch(cls, batch_id, extra_ingredients=None, extra_containers=None, extra_consumables=None):
        """Add extra ingredients, containers, and consumables to an in-progress batch"""
        try:
            batch = db.session.get(Batch, batch_id)
            if not batch:
                return False, "Batch not found", []

            if batch.status != 'in_progress':
                return False, "Can only add items to in-progress batches", []

            # Enforce organization ownership for security
            if batch.organization_id != current_user.organization_id:
                return False, "Permission denied", []

            extra_ingredients = extra_ingredients or []
            extra_containers = extra_containers or []
            extra_consumables = extra_consumables or []
            errors = []

            from app.services.stock_check import UniversalStockCheckService
            from app.services.stock_check.types import InventoryCategory
            uscs = UniversalStockCheckService()

            # Process extra containers
            for container in extra_containers:
                container_item = db.session.get(InventoryItem, container["item_id"])
                if not container_item:
                    errors.append({"item": "Unknown", "message": "Container not found"})
                    continue

                needed_amount = float(container["quantity"])
                reason = container.get("reason", "batch")

                # Validate reason
                valid_reasons = ["extra_yield", "damaged"]
                if reason not in valid_reasons:
                    errors.append({"item": container_item.name, "message": f"Invalid reason: {reason}"})
                    continue

                # Check stock via USCS (single item)
                sc_result = uscs.check_single_item(
                    item_id=container_item.id,
                    quantity_needed=needed_amount,
                    unit=(container_item.unit or 'count'),
                    category=InventoryCategory.CONTAINER
                )

                available_qty = sc_result.available_quantity if hasattr(sc_result, 'available_quantity') else float(container_item.quantity or 0)
                if sc_result.status.name in ['NEEDED', 'OUT_OF_STOCK', 'ERROR'] or available_qty < needed_amount:
                    errors.append({
                        "item": container_item.name,
                        "message": sc_result.error_message or f"Not enough in stock. Available: {available_qty}, Needed: {needed_amount}",
                        "needed": needed_amount,
                        "available": available_qty,
                        "needed_unit": "units"
                    })
                    continue

                # Deduct inventory
                adjustment_type = "damaged" if reason == "damaged" else "batch"
                success, message = process_inventory_adjustment(
                    item_id=container_item.id,
                    quantity=-needed_amount,
                    change_type=adjustment_type,
                    unit=(container_item.unit or 'count'),
                    notes=f"Extra container for batch {batch.label_code} - {reason}",
                    batch_id=batch.id,
                    created_by=current_user.id,
                    defer_commit=True
                )

                if not success:
                    errors.append({
                        "item": container_item.name,
                        "message": message or "Failed to deduct from inventory",
                        "needed": needed_amount,
                        "needed_unit": "units"
                    })
                    continue

                # Snapshot extra container cost via history aggregation (DRY)
                try:
                    from app.services.costing_engine import weighted_unit_cost_for_batch_item
                    extra_container_cost = weighted_unit_cost_for_batch_item(container_item.id, batch.id)
                except Exception:
                    extra_container_cost = float(container_item.cost_per_unit or 0.0)

                new_extra = ExtraBatchContainer(
                    batch_id=batch.id,
                    container_id=container_item.id,
                    container_quantity=int(needed_amount),
                    quantity_used=int(needed_amount),
                    cost_each=extra_container_cost,
                    reason=reason,
                    organization_id=current_user.organization_id
                )
                db.session.add(new_extra)

            # Process extra ingredients
            for item in extra_ingredients:
                inventory_item = db.session.get(InventoryItem, item["item_id"])
                if not inventory_item:
                    continue

                try:
                    needed_quantity = float(item["quantity"])
                    requested_unit = item.get("unit") or inventory_item.unit

                    # USCS single-item stock check handles conversion + FIFO availability
                    sc_result = uscs.check_single_item(
                        item_id=inventory_item.id,
                        quantity_needed=needed_quantity,
                        unit=requested_unit,
                        category=InventoryCategory.INGREDIENT
                    )

                    if sc_result.status.value in ['needed', 'out_of_stock', 'error']:
                        errors.append({
                            "item": inventory_item.name,
                            "message": sc_result.error_message or "Not enough in stock",
                            "needed": getattr(sc_result, 'needed_quantity', None),
                            "needed_unit": sc_result.needed_unit
                        })
                        continue

                    # Use centralized inventory adjustment (USCS already normalized unit for availability; core will normalize unit for deduction)
                    success, message = process_inventory_adjustment(
                        item_id=inventory_item.id,
                        quantity=-float(sc_result.needed_quantity),
                        change_type='batch',
                        unit=requested_unit,
                        notes=f"Extra ingredient for batch {batch.label_code}",
                        batch_id=batch.id,
                        created_by=current_user.id,
                        defer_commit=True
                    )

                    if not success:
                        normalized_message = message or "Not enough in stock"
                        try:
                            if isinstance(normalized_message, str) and normalized_message.lower().startswith("insufficient inventory"):
                                normalized_message = f"Not enough in stock. {normalized_message}"
                        except Exception:
                            pass
                        errors.append({
                            "item": inventory_item.name,
                            "message": normalized_message,
                            "needed": float(needed_quantity),
                            "needed_unit": inventory_item.unit
                        })
                    else:
                        # Snapshot extra ingredient cost via history aggregation (DRY)
                        try:
                            from app.services.costing_engine import weighted_unit_cost_for_batch_item
                            extra_ing_cost = weighted_unit_cost_for_batch_item(inventory_item.id, batch.id)
                        except Exception:
                            extra_ing_cost = float(inventory_item.cost_per_unit or 0.0)

                        new_extra = ExtraBatchIngredient(
                            batch_id=batch.id,
                            inventory_item_id=inventory_item.id,
                            quantity_used=float(sc_result.needed_quantity),
                            unit=inventory_item.unit,
                            cost_per_unit=extra_ing_cost,
                            organization_id=current_user.organization_id
                        )
                        db.session.add(new_extra)

                except ValueError as e:
                    errors.append({
                        "item": inventory_item.name,
                        "message": str(e)
                    })

            # Process extra consumables
            for cons in extra_consumables:
                consumable_item = db.session.get(InventoryItem, cons["item_id"])
                if not consumable_item:
                    errors.append({"item": "Unknown", "message": "Consumable not found"})
                    continue

                try:
                    needed_quantity = float(cons["quantity"])
                    requested_unit = cons.get("unit") or consumable_item.unit

                    sc_result = uscs.check_single_item(
                        item_id=consumable_item.id,
                        quantity_needed=needed_quantity,
                        unit=requested_unit,
                        category=InventoryCategory.INGREDIENT
                    )

                    if sc_result.status.value in ['needed', 'out_of_stock', 'error']:
                        errors.append({
                            "item": consumable_item.name,
                            "message": sc_result.error_message or "Not enough in stock",
                            "needed": sc_result.needed_quantity,
                            "needed_unit": sc_result.needed_unit
                        })
                        continue

                    # Deduct inventory
                    success, message = process_inventory_adjustment(
                        item_id=consumable_item.id,
                        quantity=-float(sc_result.needed_quantity),
                        change_type='batch',
                        unit=requested_unit,
                        notes=f"Extra consumable for batch {batch.label_code}",
                        batch_id=batch.id,
                        created_by=current_user.id,
                        defer_commit=True
                    )

                    if not success:
                        normalized_message = message or "Not enough in stock"
                        try:
                            if isinstance(normalized_message, str) and normalized_message.lower().startswith("insufficient inventory"):
                                normalized_message = f"Not enough in stock. {normalized_message}"
                        except Exception:
                            pass
                        errors.append({
                            "item": consumable_item.name,
                            "message": normalized_message,
                            "needed": needed_quantity,
                            "needed_unit": consumable_item.unit
                        })
                        continue

                    # Snapshot extra consumable per costing engine (DRY)
                    from app.models.batch import ExtraBatchConsumable
                    try:
                        from app.services.costing_engine import weighted_unit_cost_for_batch_item
                        extra_cons_cost = weighted_unit_cost_for_batch_item(consumable_item.id, batch.id)
                    except Exception:
                        extra_cons_cost = float(consumable_item.cost_per_unit or 0.0)

                    extra_rec = ExtraBatchConsumable(
                        batch_id=batch.id,
                        inventory_item_id=consumable_item.id,
                        quantity_used=float(sc_result.needed_quantity),
                        unit=consumable_item.unit,
                        cost_per_unit=extra_cons_cost,
                        organization_id=current_user.organization_id
                    )
                    db.session.add(extra_rec)

                except ValueError as e:
                    errors.append({
                        "item": consumable_item.name,
                        "message": str(e)
                    })

            if errors:
                return False, "Some items could not be added", errors

            db.session.commit()
            return True, "Items added successfully", []

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding extra items to batch: {str(e)}")
            return False, str(e), []