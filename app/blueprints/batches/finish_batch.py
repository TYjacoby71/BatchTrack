"""Finish batch routes.

Synopsis:
Completes or fails batches via service delegation.

Glossary:
- Completion: Finalizes batch outputs and inventory effects.
- Failure: Marks a batch as failed without output creation.
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils.permissions import require_permission, has_permission, has_tier_permission
from ...models import db, Batch, Product, ProductVariant, InventoryItem
from ...models.inventory_lot import InventoryLot
from ...models.product import ProductSKU
from ...services.inventory_adjustment import process_inventory_adjustment
from app.utils.permissions import role_required

finish_batch_bp = Blueprint('finish_batch', __name__)
logger = logging.getLogger(__name__)


def _parse_adjustment_result(result):
    """Strictly parse canonical adjustment return shape (success, message)."""
    if not isinstance(result, tuple) or len(result) < 2:
        raise TypeError(
            "process_inventory_adjustment must return (success, message)"
        )
    success = bool(result[0])
    message = str(result[1]) if result[1] is not None else ""
    return success, message


# =========================================================
# FINISH BATCH
# =========================================================
# --- Complete batch ---
# Purpose: Complete a batch and create final outputs.
@finish_batch_bp.route('/<int:batch_id>/complete', methods=['POST'])
@login_required
@require_permission('batches.finish')
def complete_batch(batch_id):
    """Complete a batch and create final products/ingredients - thin controller"""
    try:
        from ...services.batch_service import BatchOperationsService

        # Delegate to service
        success, message = BatchOperationsService.complete_batch(batch_id, request.form)

        if success:
            flash(message, 'success')
            return redirect(url_for('batches.list_batches'))
        else:
            flash(message, 'error')
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

        # The actual completion logic has been moved to BatchOperationsService.complete_batch()
        # This delegates to the existing _complete_batch_internal function below

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing batch {batch_id}: {str(e)}")
        flash(f'Error completing batch: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))


# --- Fail batch ---
# Purpose: Mark a batch as failed via service.
@finish_batch_bp.route('/<int:batch_id>/fail', methods=['POST'])
@login_required
@require_permission('batches.finish')
def fail_batch(batch_id):
    """Mark a batch as failed via service. Thin controller.

    Ensures the batch is no longer in progress and sets status to failed.
    """
    try:
        from ...services.batch_service import BatchOperationsService

        reason = request.form.get('reason') or request.json.get('reason') if request.is_json else None
        success, message = BatchOperationsService.fail_batch(batch_id, reason)

        if request.is_json:
            status_code = 200 if success else 400
            return jsonify({'success': success, 'message': message}), status_code

        if success:
            flash(message, 'success')
            return redirect(url_for('batches.list_batches'))
        else:
            flash(message, 'error')
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error failing batch {batch_id}: {str(e)}")
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error failing batch: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))


def _complete_batch_internal(batch_id, form_data):
    """Internal batch completion logic - called by service"""
    try:
        # Get the batch with conditional organization scoping
        org_id = getattr(current_user, 'organization_id', None)
        query = Batch.query.filter_by(id=batch_id, status='in_progress')
        if org_id:
            query = query.filter_by(organization_id=org_id)
        batch = query.first()

        if not batch:
            return False, 'Batch not found or already completed'

        org_tracks_batch_outputs = has_tier_permission(
            'batches.track_inventory_outputs',
            default_if_missing_catalog=False,
        )
        requested_output_type = (form_data.get('output_type') or '').strip()
        output_type = requested_output_type or (batch.batch_type or 'ingredient')
        can_create_product_output = has_permission(current_user, 'products.create')

        if not org_tracks_batch_outputs or batch.batch_type == 'untracked':
            output_type = 'untracked'

        # Enforce plan-based product lock server-side regardless of client payload.
        if output_type == 'product' and not can_create_product_output:
            logger.info(
                "🔒 BATCH COMPLETION: User %s lacks products.create; forcing ingredient output for batch %s",
                getattr(current_user, 'id', None),
                batch_id,
            )
            output_type = 'ingredient'

        # Pre-validate FIFO sync for any product SKUs that will be created
        if output_type == 'product':
            product_id = form_data.get('product_id')
            variant_id = form_data.get('variant_id')

            if product_id and variant_id:
                # Check existing SKUs that might be updated
                from app.services.product_service import ProductService
                from app.models.product import ProductSKU
                from app.services.inventory_adjustment import validate_inventory_fifo_sync

                # Get potential SKUs that could be affected
                inv_org_id = (getattr(current_user, 'organization_id', None) or batch.organization_id)
                existing_skus_query = ProductSKU.query.join(ProductSKU.inventory_item).filter(
                    ProductSKU.product_id == product_id,
                    ProductSKU.variant_id == variant_id
                )
                if inv_org_id:
                    existing_skus_query = existing_skus_query.filter(InventoryItem.organization_id == inv_org_id)
                existing_skus = existing_skus_query.all()

                for sku in existing_skus:
                    is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(sku.inventory_item_id, 'product')
                    if not is_valid:
                        return False, f'Cannot complete batch - inventory sync error for existing SKU {sku.sku_code}: {error_msg}'

        # Get form data
        final_quantity = float(form_data.get('final_quantity', 0))
        output_unit = form_data.get('output_unit')
        final_portions = None
        try:
            if getattr(batch, 'is_portioned', False):
                final_portions = int(form_data.get('final_portions') or 0)
                if final_portions <= 0:
                    return False, 'Final portions must be provided for portioned batches'
        except Exception:
            return False, 'Invalid final portions value'

        # Perishable settings
        is_perishable = form_data.get('is_perishable') == 'on'
        shelf_life_days = None
        expiration_date = None

        if is_perishable:
            shelf_life_days = int(form_data.get('shelf_life_days', 0))
            exp_date_str = form_data.get('expiration_date')
            if exp_date_str:
                expiration_date = datetime.strptime(exp_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)

        # Update batch with completion data
        batch.final_quantity = final_quantity
        batch.output_unit = output_unit
        batch.status = 'completed'
        batch.completed_at = datetime.now(timezone.utc)
        batch.is_perishable = is_perishable
        batch.shelf_life_days = shelf_life_days
        batch.expiration_date = expiration_date

        output_metrics = None

        # Route based on batch_type (primary) and output_type (secondary)
        # batch_type determines the intended output, output_type is user selection
        if output_type == 'untracked':
            logger.info(
                "🔒 BATCH COMPLETION: Recording untracked batch output for %s with inventory posting disabled",
                batch.label_code,
            )
            batch.batch_type = 'untracked'
        elif batch.batch_type == 'ingredient' or output_type == 'ingredient':
            # Handle intermediate ingredient creation
            logger.info(f"🔧 BATCH COMPLETION: Creating intermediate ingredient for batch_type='{batch.batch_type}', output_type='{output_type}'")
            _create_intermediate_ingredient(batch, final_quantity, output_unit, expiration_date)
        else:
            # Handle product creation (batch_type='product' or default)
            logger.info(f"🔧 BATCH COMPLETION: Creating product output for batch_type='{batch.batch_type}', output_type='{output_type}'")
            product_id = form_data.get('product_id')
            variant_id = form_data.get('variant_id')

            if not product_id or not variant_id:
                return False, 'Product and variant selection required'

            output_metrics = _create_product_output(batch, product_id, variant_id, final_quantity, output_unit, expiration_date, form_data, final_portions=final_portions)

        # Persist fill efficiency to BatchStats if available (post output creation)
        try:
            from app.models.statistics import BatchStats as _BatchStats
            stats = _BatchStats.query.filter_by(batch_id=batch.id).first()
            if stats and batch.final_quantity and output_unit:
                # If product output path computed container volume, use it
                total_container_volume = None
                if isinstance(locals().get('output_metrics'), dict):
                    total_container_volume = output_metrics.get('total_container_volume')

                if total_container_volume and total_container_volume > 0:
                    actual_in_containers = min(float(batch.final_quantity), float(total_container_volume))
                    stats.actual_fill_efficiency = (actual_in_containers / float(total_container_volume)) * 100.0
                else:
                    # Fallback: if no containers involved, treat as N/A (leave default)
                    pass
        except Exception:
            pass

        try:
            db.session.commit()
            return True, f'Batch {batch.label_code} completed successfully!'
        except Exception as commit_error:
            db.session.rollback()
            return False, f'Failed to complete batch due to database error: {str(commit_error)}'

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing batch {batch_id}: {str(e)}")
        return False, f'Error completing batch: {str(e)}'


def _create_intermediate_ingredient(batch, final_quantity, output_unit, expiration_date):
    """Create intermediate ingredient from batch completion"""
    try:
        # Create or get inventory item for the intermediate ingredient
        ingredient_name = f"{batch.recipe.name} (Intermediate)"

        inventory_item = InventoryItem.query.filter_by(
            name=ingredient_name,
            organization_id=(getattr(current_user, 'organization_id', None) or batch.organization_id)
        ).first()

        if not inventory_item:
            inventory_item = InventoryItem(
                name=ingredient_name,
                unit=output_unit,
                type='ingredient',  # Set the type properly
                intermediate=True,  # Mark as intermediate ingredient
                organization_id=(getattr(current_user, 'organization_id', None) or batch.organization_id),
                created_by=(getattr(current_user, 'id', None) or batch.created_by)
            )
            db.session.add(inventory_item)
            db.session.flush()  # Ensure we get the ID

        # Set perishable data at the inventory_item level from batch
        if batch.is_perishable:
            inventory_item.is_perishable = True
            inventory_item.shelf_life_days = batch.shelf_life_days

        # Process inventory adjustment through CANONICAL entry point
        logger.info(f"🔧 INTERMEDIATE INGREDIENT: Adding {final_quantity} {output_unit} to inventory item {inventory_item.id}")
        adjustment_result = process_inventory_adjustment(
            item_id=inventory_item.id,
            quantity=final_quantity,
            change_type='finished_batch',
            unit=output_unit,
            notes=f'Batch {batch.label_code} completed',
            created_by=(getattr(current_user, 'id', None) or batch.created_by),
            custom_expiration_date=expiration_date,
            batch_id=batch.id  # Add batch traceability
        )
        success, error_message = _parse_adjustment_result(adjustment_result)

        if not success:
            raise ValueError(error_message or "Failed to add intermediate ingredient inventory via canonical service")

        logger.info(f"Created intermediate ingredient via canonical service: {ingredient_name}, quantity: {final_quantity} {output_unit}")

    except Exception as e:
        logger.error(f"Error creating intermediate ingredient via canonical service: {str(e)}")
        raise


def _create_product_output(batch, product_id, variant_id, final_quantity, output_unit, expiration_date, form_data, final_portions: int | None = None):
    """Create product SKUs from batch completion using centralized inventory adjustment"""
    try:
        # Get product and variant with proper organization scoping
        product = Product.query.filter_by(
            id=product_id,
            organization_id=(getattr(current_user, 'organization_id', None) or batch.organization_id)
        ).first()

        variant = ProductVariant.query.filter_by(
            id=variant_id,
            product_id=product_id,
            organization_id=(getattr(current_user, 'organization_id', None) or batch.organization_id)
        ).first()

        if not product:
            product = Product.query.filter_by(id=product_id).first()
        if not variant:
            variant = ProductVariant.query.filter_by(id=variant_id, product_id=product_id).first()

        if not product or not variant:
            raise ValueError("Invalid product or variant selection")

        # Calculate total ingredient-only cost for allocation (consumables handled separately)
        total_ingredient_cost = 0

        # Add regular batch ingredients
        for ing in batch.batch_ingredients:
            total_ingredient_cost += (ing.quantity_used or 0) * (ing.cost_per_unit or 0)

        # Add extra ingredients
        for extra in batch.extra_ingredients:
            total_ingredient_cost += (extra.quantity_used or 0) * (extra.cost_per_unit or 0)

        # Calculate ingredient unit cost (cost per unit of final product volume)
        ingredient_unit_cost = total_ingredient_cost / final_quantity if final_quantity > 0 else 0

        logger.info(f"Batch {batch.label_code}: Total ingredient cost ${total_ingredient_cost:.2f}, Unit cost ${ingredient_unit_cost:.2f} per {output_unit}")

        # Process container allocations with cost calculation
        container_skus, container_lots = _process_container_allocations(batch, product, variant, form_data, expiration_date, ingredient_unit_cost)
        created_lots = [lot for lot in container_lots if lot]

        # Calculate total product volume used in containers
        total_container_volume = 0
        for sku_info in container_skus:
            # Each container holds capacity * number of containers
            container_capacity = sku_info.get('container_capacity', 1)
            container_count = sku_info.get('quantity', 0)
            total_container_volume += container_capacity * container_count

        # Calculate bulk quantity (remaining after containers)
        bulk_quantity = max(0, final_quantity - total_container_volume)

        # Create bulk SKU if there's remaining quantity and not portioned
        if bulk_quantity > 0 and not getattr(batch, 'is_portioned', False):
            bulk_unit = output_unit
            # No product base unit; units are defined at SKU/Inventory level

            bulk_sku, bulk_lot = _create_bulk_sku(product, variant, bulk_quantity, bulk_unit, expiration_date, batch, ingredient_unit_cost)
            if bulk_lot:
                logger.info(f"Bulk quantity tied to lot {bulk_lot.display_code} (ID {bulk_lot.id})")
                created_lots.append(bulk_lot)

        # For portioned batches, create portion-based SKU if final_portions provided
        if getattr(batch, 'is_portioned', False) and final_portions and final_portions > 0:
            try:
                # Build portion-based size label
                size_label = _derive_size_label_from_portions(batch, final_quantity, output_unit, final_portions)
                size_label = ' '.join((size_label or 'Portion').split())

                # Portion unit cost: divide total batch ingredient cost by actual portion yield
                try:
                    portion_unit_cost = total_ingredient_cost / float(final_portions)
                except Exception:
                    portion_unit_cost = ingredient_unit_cost

                # Fetch or create SKU tied to provided product/variant within batch org context
                from ...models.product import ProductSKU
                from ...models import InventoryItem

                sku = ProductSKU.query.filter_by(
                    product_id=product.id,
                    variant_id=variant.id,
                    size_label=size_label
                ).first()

                if not sku:
                    # Create inventory item for the SKU
                    inv = InventoryItem(
                        name=f"{product.name} - {variant.name} - {size_label}",
                        type='product',
                        unit='count',
                        quantity=0.0,
                        organization_id=batch.organization_id,
                        created_by=batch.created_by
                    )
                    db.session.add(inv)
                    db.session.flush()

                    # Generate a simple SKU code using model helper
                    sku_code = ProductSKU.generate_sku_code(product.name, variant.name, size_label)

                    # Optional: render human-friendly name
                    try:
                        from ...services.sku_name_builder import SKUNameBuilder
                        from ...models.product_category import ProductCategory
                        category = db.session.get(ProductCategory, product.category_id) if getattr(product, 'category_id', None) else None
                        template = (category.sku_name_template if category and category.sku_name_template else None) or '{variant} {product} ({size_label})'
                        naming_context = {
                            'yield_value': final_quantity,
                            'yield_unit': output_unit,
                            'portion_name': getattr(batch, 'portion_name', None) or 'Unit',
                            'portion_count': final_portions,
                        }
                        base_context = {
                            'product': product.name,
                            'variant': variant.name,
                            'container': None,
                            'size_label': size_label,
                        }
                        base_context.update(naming_context)
                        sku_name = SKUNameBuilder.render(template, base_context)
                    except Exception:
                        sku_name = f"{product.name} - {variant.name} - {size_label}"

                    sku = ProductSKU(
                        product_id=product.id,
                        variant_id=variant.id,
                        size_label=size_label,
                        sku_code=sku_code,
                        sku=sku_code,
                        sku_name=sku_name,
                        inventory_item_id=inv.id,
                        unit='count',
                        organization_id=batch.organization_id,
                        created_by=batch.created_by
                    )
                    db.session.add(sku)
                    db.session.flush()

                # Credit inventory as number of portions to the SKU's inventory item
                adjustment_result = process_inventory_adjustment(
                    item_id=sku.inventory_item_id,
                    quantity=final_portions,
                    change_type='finished_batch',
                    unit='count',
                    notes=f'Batch {batch.label_code} completed - {final_portions} portions',
                    created_by=(getattr(current_user, 'id', None) or batch.created_by),
                    custom_expiration_date=expiration_date,
                    cost_override=portion_unit_cost,
                    batch_id=batch.id
                )
                success, error_message = _parse_adjustment_result(adjustment_result)
                if not success:
                    raise ValueError(error_message or 'Failed to credit portion inventory')

                portion_lot = InventoryLot.query.filter_by(
                    inventory_item_id=sku.inventory_item_id,
                    batch_id=batch.id
                ).order_by(InventoryLot.created_at.desc()).first()
                if portion_lot:
                    logger.info(f"Portion SKU {sku.sku_code} tied to lot {portion_lot.display_code} (ID {portion_lot.id})")
                    created_lots.append(portion_lot)
            except Exception as e:
                logger.error(f"Error creating portion-based SKU: {e}")
                raise

        logger.info(f"Created product output for batch {batch.label_code}: {len(container_skus)} container SKUs, {bulk_quantity if not getattr(batch, 'is_portioned', False) else 0} {bulk_unit if (bulk_quantity > 0 and not getattr(batch, 'is_portioned', False)) else ''} bulk")
        return {'total_container_volume': total_container_volume, 'created_lots': [lot for lot in created_lots if lot]}

    except Exception as e:
        logger.error(f"Error creating product output: {str(e)}")
        raise


def _derive_size_label_from_portions(batch, final_bulk_quantity, bulk_unit, final_portions):
    """Derive size label like '4 oz Bar' from bulk and portion count with simple division.

    Uses the batch output unit directly; no implicit conversions here.
    """
    try:
        if not final_portions or final_portions <= 0:
            return 'Portion'
        per_portion = round(float(final_bulk_quantity) / float(final_portions), 2)
        portion_name = getattr(batch, 'portion_name', None) or 'Unit'
        unit = bulk_unit
        return f"{per_portion} {unit} {portion_name}"
    except Exception:
        return 'Portion'

def _process_container_allocations(batch, product, variant, form_data, expiration_date, ingredient_unit_cost):
    """Process container allocations and create SKUs"""
    container_skus = []
    created_lots = []

    # Calculate total containers used vs passed to product for cost allocation
    container_usage = {}  # container_id -> {'used': total_used, 'passed': passed_to_product}

    # First pass: calculate total used for each container type
    for container in batch.containers:
        container_id = container.container_id
        if container_id not in container_usage:
            container_usage[container_id] = {'used': 0, 'passed': 0, 'cost_each': container.cost_each or 0}
        container_usage[container_id]['used'] += container.quantity_used or 0

    for extra_container in batch.extra_containers:
        container_id = extra_container.container_id
        if container_id not in container_usage:
            container_usage[container_id] = {'used': 0, 'passed': 0, 'cost_each': extra_container.cost_each or 0}
        container_usage[container_id]['used'] += extra_container.quantity_used or 0

    # Process containers by container_final_X keys from the combined form
    container_final_keys = [k for k in form_data.keys() if k.startswith('container_final_')]

    for key in container_final_keys:
        container_id = key.replace('container_final_', '')
        final_quantity = int(form_data.get(key, 0))

        if final_quantity > 0:
            try:
                # Get container with simple query
                container_item = InventoryItem.query.filter_by(
                    id=int(container_id),
                    organization_id=(getattr(current_user, 'organization_id', None) or batch.organization_id)
                ).first()

                if not container_item:
                    logger.error(f"Container with ID {container_id} not found for organization {(getattr(current_user, 'organization_id', None) or batch.organization_id)}")
                    continue

                # Update passed quantity for cost calculation
                container_usage[int(container_id)]['passed'] = final_quantity

                # Calculate adjusted container cost per unit
                usage_info = container_usage[int(container_id)]
                total_container_cost = usage_info['cost_each'] * usage_info['used']
                adjusted_container_cost_per_unit = total_container_cost / final_quantity if final_quantity > 0 else usage_info['cost_each']

                # Debug logging
                logger.info(f"Processing container: {container_item.name} (ID: {container_item.id}), {final_quantity} containers")
                logger.info(f"Container cost calculation: {usage_info['used']} used × ${usage_info['cost_each']} = ${total_container_cost}, divided by {final_quantity} passed = ${adjusted_container_cost_per_unit:.2f} per container")

                # Create container SKU - final_quantity is number of containers
                container_sku, container_lot = _create_container_sku(
                    product=product,
                    variant=variant,
                    container_item=container_item,
                    quantity=final_quantity,  # Number of containers
                    batch=batch,
                    expiration_date=expiration_date,
                    ingredient_unit_cost=ingredient_unit_cost,
                    adjusted_container_cost=adjusted_container_cost_per_unit
                )

                # Track container info for volume calculation
                container_skus.append({
                    'sku': container_sku,
                    'quantity': final_quantity,  # Number of containers
                    'container_capacity': container_item.capacity or 1  # Volume per container
                })

                if container_lot:
                    created_lots.append(container_lot)

                logger.info(f"Created container SKU for {final_quantity} x {container_item.name} containers")

            except Exception as e:
                logger.error(f"Error processing container {container_id}: {e}")
                import traceback
                logger.error(f"Container processing traceback: {traceback.format_exc()}")
                continue

    return container_skus, created_lots


def _create_container_sku(product, variant, container_item, quantity, batch, expiration_date, ingredient_unit_cost, adjusted_container_cost):
    """Create or get existing container SKU using ProductService"""
    try:
        logger.info(f"Creating container SKU with container: {container_item.name}, quantity: {quantity}")

        # Create size label format: "[capacity] [capacity_unit] [container_name]"
        # Example: "8 fl oz Bottle"
        if container_item.capacity and container_item.capacity_unit:
            # Build from structured attributes
            cap_str = f"{container_item.capacity} {container_item.capacity_unit}".strip()
            try:
                display_name = container_item.container_display_name
            except Exception:
                display_name = container_item.name
            size_label = f"{cap_str} {display_name}".strip()
        else:
            # No capacity specified; fall back to derived display name
            try:
                display_name = container_item.container_display_name
            except Exception:
                display_name = container_item.name
            size_label = display_name
        # Final sanitize
        size_label = ' '.join((size_label or '').split())

        # Calculate total cost per container unit
        # Cost = (ingredient cost per unit × container capacity) + adjusted container cost
        container_capacity = container_item.capacity or 1
        ingredient_cost_per_container = ingredient_unit_cost * container_capacity
        total_cost_per_container = ingredient_cost_per_container + adjusted_container_cost

        logger.info(f"Container cost breakdown: ${ingredient_cost_per_container:.2f} ingredients + ${adjusted_container_cost:.2f} container = ${total_cost_per_container:.2f} per container")

        # Use ProductService to get or create the SKU - this handles existing SKUs properly
        from ...services.product_service import ProductService
        naming_context = {
            'container': size_label,
            'yield_value': batch.final_quantity,
            'yield_unit': batch.output_unit,
        }

        product_sku = ProductService.get_or_create_sku(
            product_name=product.name,
            variant_name=variant.name,
            size_label=size_label,
            unit='count',  # Containers are always counted as individual units
            naming_context=naming_context
        )

        # Ensure sku_name follows category template for container flows
        try:
            from ...services.sku_name_builder import SKUNameBuilder
            from ...models.product_category import ProductCategory
            category = db.session.get(ProductCategory, product.category_id) if getattr(product, 'category_id', None) else None
            template = (category.sku_name_template if category and category.sku_name_template else None) or '{variant} {product} ({container})'
            base_context = {
                'product': product.name,
                'variant': variant.name,
                'container': size_label,
                'size_label': None
            }
            base_context.update(naming_context)
            product_sku.sku_name = SKUNameBuilder.render(template, base_context)
        except Exception:
            pass

        # Set perishable data at the inventory_item level from batch
        if product_sku.inventory_item and batch.is_perishable:
            product_sku.inventory_item.is_perishable = True
            product_sku.inventory_item.shelf_life_days = batch.shelf_life_days

        # Add containers to inventory - quantity is number of containers
        adjustment_result = process_inventory_adjustment(
            item_id=product_sku.inventory_item_id,
            quantity=quantity,  # Number of containers
            change_type='finished_batch',
            unit='count',  # Unit is count for containers
            notes=f'Batch {batch.label_code} completed - {quantity} containers of {size_label}',
            created_by=(getattr(current_user, 'id', None) or batch.created_by),
            custom_expiration_date=expiration_date,
            cost_override=total_cost_per_container,  # Pass calculated cost per container
            batch_id=batch.id
        )
        success, error_message = _parse_adjustment_result(adjustment_result)

        if not success:
            raise ValueError(error_message or f"Failed to add container inventory for {size_label}")

        logger.info(f"Successfully created/updated container SKU: {product_sku.sku_code} with {quantity} containers at ${total_cost_per_container:.2f} per container")

        new_lot = InventoryLot.query.filter_by(
            inventory_item_id=product_sku.inventory_item_id,
            batch_id=batch.id
        ).order_by(InventoryLot.created_at.desc()).first()

        if new_lot:
            logger.info(f"Linked container SKU {product_sku.sku_code} to lot {new_lot.display_code} (ID {new_lot.id})")

        return product_sku, new_lot

    except Exception as e:
        logger.error(f"Error creating container SKU: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise


def _create_bulk_sku(product, variant, quantity, unit, expiration_date, batch, ingredient_unit_cost):
    """Create or update bulk SKU for remaining quantity using ProductService"""
    try:
        # Use ProductService to get or create the bulk SKU
        from ...services.product_service import ProductService
        bulk_sku = ProductService.get_or_create_sku(
            product_name=product.name,
            variant_name=variant.name,
            size_label='Bulk',
            unit=unit  # Use the batch output unit
        )

        # Set perishable data at the inventory_item level from batch
        if bulk_sku.inventory_item and batch.is_perishable:
            bulk_sku.inventory_item.is_perishable = True
            bulk_sku.inventory_item.shelf_life_days = batch.shelf_life_days

        # Add bulk quantity to inventory with calculated unit cost
        adjustment_result = process_inventory_adjustment(
            item_id=bulk_sku.inventory_item_id,
            quantity=quantity,
            change_type='finished_batch',
            unit=unit,
            notes=f'Batch {batch.label_code} completed - bulk remainder',
            created_by=(getattr(current_user, 'id', None) or batch.created_by),
            custom_expiration_date=expiration_date,
            cost_override=ingredient_unit_cost,  # Pass ingredient unit cost for bulk
            batch_id=batch.id
        )
        success, error_message = _parse_adjustment_result(adjustment_result)

        if not success:
            raise ValueError(error_message or f"Failed to add bulk inventory for {quantity} {unit}")

        logger.info(f"Created/updated bulk SKU: {bulk_sku.sku_code} with {quantity} {unit} at ${ingredient_unit_cost:.2f} per {unit}")
        bulk_lot = InventoryLot.query.filter_by(
            inventory_item_id=bulk_sku.inventory_item_id,
            batch_id=batch.id
        ).order_by(InventoryLot.created_at.desc()).first()

        if bulk_lot:
            logger.info(f"Linked bulk SKU {bulk_sku.sku_code} to lot {bulk_lot.display_code} (ID {bulk_lot.id})")

        return bulk_sku, bulk_lot

    except Exception as e:
        logger.error(f"Error creating bulk SKU: {str(e)}")
        raise