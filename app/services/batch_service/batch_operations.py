import logging
from datetime import datetime
from sqlalchemy import extract
from flask_login import current_user

from app.models import db, Batch, Recipe, InventoryItem, BatchContainer, BatchIngredient
from app.models.batch import BatchConsumable
from app import models
from app.models import ExtraBatchIngredient, ExtraBatchContainer, Product, ProductVariant
from app.services.unit_conversion import ConversionEngine
from app.services.inventory_adjustment import process_inventory_adjustment, validate_inventory_fifo_sync
from app.utils.timezone_utils import TimezoneUtils
from app.utils.code_generator import generate_batch_label_code
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class BatchOperationsService(BaseService):
    """Service for batch lifecycle operations: start, finish, cancel"""

    @classmethod
    def start_batch(cls, recipe_id, scale=1.0, batch_type='ingredient', notes='', containers_data=None, requires_containers=False):
        """Start a new batch with inventory deductions atomically. Rolls back on any failure."""
        try:
            recipe = Recipe.query.get(recipe_id)
            if not recipe:
                return None, "Recipe not found"

            scale = float(scale)
            containers_data = containers_data or []

            # Generate batch label via centralized generator
            label_code = generate_batch_label_code(recipe)

            projected_yield = scale * recipe.predicted_yield

            # Create the batch
            batch = Batch(
                recipe_id=recipe_id,
                label_code=label_code,
                batch_type=batch_type,
                projected_yield=projected_yield,
                projected_yield_unit=recipe.predicted_yield_unit,
                scale=scale,
                status='in_progress',
                notes=notes,
                created_by=current_user.id,
                organization_id=current_user.organization_id,
                started_at=TimezoneUtils.utc_now()
            )

            db.session.add(batch)

            # Handle containers if required
            container_errors = []
            if requires_containers:
                container_errors = cls._process_batch_containers(batch, containers_data, defer_commit=True)

            # Process ingredient deductions
            ingredient_errors = cls._process_batch_ingredients(batch, recipe, scale, defer_commit=True)

            # Process consumable deductions
            consumable_errors = cls._process_batch_consumables(batch, recipe, scale, defer_commit=True)

            # Combine all errors
            all_errors = container_errors + ingredient_errors + consumable_errors

            if all_errors:
                # Any deduction failure should abort the entire start
                db.session.rollback()
                return None, all_errors
            else:
                # All deductions validated; commit once atomically
                db.session.commit()
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
                    container_item = InventoryItem.query.get(container_id)
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
                                # Create BatchContainer record
                                bc = BatchContainer(
                                    batch_id=batch.id,
                                    container_id=container_id,
                                    container_quantity=quantity,
                                    quantity_used=quantity,
                                    cost_each=container_item.cost_per_unit or 0.0,
                                    organization_id=current_user.organization_id
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
    def _process_batch_ingredients(cls, batch, recipe, scale, defer_commit=False):
        """Process ingredient deductions for batch start"""
        errors = []
        try:
            for assoc in recipe.recipe_ingredients:
                ingredient = assoc.inventory_item
                if not ingredient:
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
                        quantity=-required_converted,
                        change_type='batch',
                        unit=ingredient.unit,
                        notes=f"Used in batch {batch.label_code}",
                        batch_id=batch.id,
                        created_by=current_user.id,
                        defer_commit=defer_commit
                    )

                    if not success:
                        errors.append(message or f"Not enough {ingredient.name} in stock.")
                        continue

                    # Create BatchIngredient record
                    batch_ingredient = BatchIngredient(
                        batch_id=batch.id,
                        inventory_item_id=ingredient.id,
                        quantity_used=required_converted,
                        unit=ingredient.unit,
                        cost_per_unit=ingredient.cost_per_unit,
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
    def _process_batch_consumables(cls, batch, recipe, scale, defer_commit=False):
        """Process consumable deductions and snapshot for batch start"""
        errors = []
        try:
            # If recipe has no consumables relationship, skip gracefully
            consumables = getattr(recipe, 'recipe_consumables', []) or []
            for assoc in consumables:
                item = assoc.inventory_item
                if not item:
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
                        quantity=-required_converted,
                        change_type='batch',
                        unit=item.unit,
                        notes=f"Consumable used in batch {batch.label_code}",
                        batch_id=batch.id,
                        created_by=current_user.id,
                        defer_commit=defer_commit
                    )

                    if not success:
                        errors.append(message or f"Not enough {item.name} in stock (consumable).")
                        continue

                    # Snapshot
                    snap = BatchConsumable(
                        batch_id=batch.id,
                        inventory_item_id=item.id,
                        quantity_used=required_converted,
                        unit=item.unit,
                        cost_per_unit=item.cost_per_unit,
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
            # Removed the import from here as it is now at the top of the file.
            # from app.services.inventory_adjustment import validate_inventory_fifo_sync

            batch = Batch.query.filter_by(
                id=batch_id,
                organization_id=current_user.organization_id
            ).first()

            if not batch:
                return False, "Batch not found"

            # Validate access and ownership
            if batch.created_by != current_user.id:
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
                container = batch_container.container
                if container:
                    process_inventory_adjustment(
                        item_id=container.id,
                        quantity=batch_container.quantity_used,
                        change_type='refunded',
                        unit=container.unit,
                        notes=f"Container refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{batch_container.quantity_used} {container.unit} of {container.name}")

            # Restore extra containers
            for extra_container in extra_containers:
                container = extra_container.container
                if container:
                    process_inventory_adjustment(
                        item_id=container.id,
                        quantity=extra_container.quantity_used,
                        change_type='refunded',
                        unit=container.unit,
                        notes=f"Extra container refunded from cancelled batch {batch.label_code}",
                        created_by=current_user.id,
                        batch_id=batch.id
                    )
                    restoration_summary.append(f"{extra_container.quantity_used} {container.unit} of {container.name}")

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
            batch.cancelled_at = datetime.utcnow()
            db.session.commit()

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

            batch = Batch.query.filter_by(
                id=batch_id,
                organization_id=current_user.organization_id,
                status='in_progress'
            ).first()

            if not batch:
                return False, 'Batch not found or already completed'

            # Delegate to internal finish batch logic
            # This maintains the existing complex logic while keeping it out of routes
            return _complete_batch_internal(batch_id, form_data)

        except Exception as e:
            logger.error(f"Error completing batch: {str(e)}")
            return False, str(e)

    @classmethod
    def add_extra_items_to_batch(cls, batch_id, extra_ingredients=None, extra_containers=None, extra_consumables=None):
        """Add extra ingredients, containers, and consumables to an in-progress batch"""
        try:
            batch = Batch.query.get(batch_id)
            if not batch:
                return False, "Batch not found", []

            if batch.status != 'in_progress':
                return False, "Can only add items to in-progress batches", []

            extra_ingredients = extra_ingredients or []
            extra_containers = extra_containers or []
            extra_consumables = extra_consumables or []
            errors = []

            # Process extra containers
            for container in extra_containers:
                container_item = InventoryItem.query.get(container["item_id"])
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

                # Check stock
                if container_item.quantity < needed_amount:
                    errors.append({
                        "item": container_item.name,
                        "message": f"Not enough in stock. Available: {container_item.quantity}, Needed: {needed_amount}",
                        "needed": needed_amount,
                        "available": container_item.quantity,
                        "needed_unit": "units"
                    })
                    continue

                # Deduct inventory
                adjustment_type = "damaged" if reason == "damaged" else "batch"
                result = process_inventory_adjustment(
                    item_id=container_item.id,
                    quantity=-needed_amount,
                    change_type=adjustment_type,
                    unit=container_item.unit,
                    notes=f"Extra container for batch {batch.label_code} - {reason}",
                    batch_id=batch.id,
                    created_by=current_user.id
                )

                if not result:
                    errors.append({
                        "item": container_item.name,
                        "message": "Failed to deduct from inventory",
                        "needed": needed_amount,
                        "needed_unit": "units"
                    })
                    continue

                # Create ExtraBatchContainer record
                new_extra = ExtraBatchContainer(
                    batch_id=batch.id,
                    container_id=container_item.id,
                    container_quantity=int(needed_amount),
                    quantity_used=int(needed_amount),
                    cost_each=container_item.cost_per_unit,
                    reason=reason,
                    organization_id=current_user.organization_id
                )
                db.session.add(new_extra)

            # Process extra ingredients
            for item in extra_ingredients:
                inventory_item = InventoryItem.query.get(item["item_id"])
                if not inventory_item:
                    continue

                try:
                    # Handle ingredient conversion
                    conversion = ConversionEngine.convert_units(
                        item["quantity"],
                        item["unit"],
                        inventory_item.unit,
                        ingredient_id=inventory_item.id,
                        density=inventory_item.density or (inventory_item.category.default_density if inventory_item.category else None)
                    )
                    needed_amount = conversion['converted_value']

                    # Use centralized inventory adjustment
                    result = process_inventory_adjustment(
                        item_id=inventory_item.id,
                        quantity=-needed_amount,
                        change_type='batch',
                        unit=inventory_item.unit,
                        notes=f"Extra ingredient for batch {batch.label_code}",
                        batch_id=batch.id,
                        created_by=current_user.id
                    )

                    if not result:
                        errors.append({
                            "item": inventory_item.name,
                            "message": "Not enough in stock",
                            "needed": needed_amount,
                            "needed_unit": inventory_item.unit
                        })
                    else:
                        # Create ExtraBatchIngredient record
                        new_extra = ExtraBatchIngredient(
                            batch_id=batch.id,
                            inventory_item_id=inventory_item.id,
                            quantity_used=needed_amount,
                            unit=inventory_item.unit,
                            cost_per_unit=inventory_item.cost_per_unit,
                            organization_id=current_user.organization_id
                        )
                        db.session.add(new_extra)

                except ValueError as e:
                    errors.append({
                        "item": inventory_item.name,
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