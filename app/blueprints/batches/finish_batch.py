import logging
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ...models import db, Batch, Product, ProductVariant, ProductSKU, InventoryItem, InventoryHistory
from ...models.product import ProductSKU
from ...services.inventory_adjustment import process_inventory_adjustment
from ..fifo.services import FIFOService

finish_batch_bp = Blueprint('finish_batch', __name__)
logger = logging.getLogger(__name__)

@finish_batch_bp.route('/batches/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    """Complete a batch and create final products/ingredients"""
    try:
        # Get the batch
        batch = Batch.query.filter_by(
            id=batch_id,
            organization_id=current_user.organization_id,
            status='in_progress'
        ).first()

        if not batch:
            flash('Batch not found or already completed', 'error')
            return redirect(url_for('batches.list_batches'))

        # Pre-validate FIFO sync for any product SKUs that will be created
        output_type = request.form.get('output_type')
        if output_type == 'product':
            product_id = request.form.get('product_id')
            variant_id = request.form.get('variant_id')

            if product_id and variant_id:
                # Check existing SKUs that might be updated
                from app.services.product_service import ProductService
                from app.models.product import ProductSKU
                from app.services.inventory_adjustment import validate_inventory_fifo_sync

                # Get potential SKUs that could be affected
                existing_skus = ProductSKU.query.join(ProductSKU.inventory_item).filter(
                    ProductSKU.product_id == product_id,
                    ProductSKU.variant_id == variant_id,
                    InventoryItem.organization_id == current_user.organization_id
                ).all()

                for sku in existing_skus:
                    is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(sku.inventory_item_id, 'product')
                    if not is_valid:
                        flash(f'Cannot complete batch - inventory sync error for existing SKU {sku.sku_code}: {error_msg}', 'error')
                        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

        # Get form data
        output_type = request.form.get('output_type')
        final_quantity = float(request.form.get('final_quantity', 0))
        output_unit = request.form.get('output_unit')

        # Perishable settings
        is_perishable = request.form.get('is_perishable') == 'on'
        shelf_life_days = None
        expiration_date = None

        if is_perishable:
            shelf_life_days = int(request.form.get('shelf_life_days', 0))
            exp_date_str = request.form.get('expiration_date')
            if exp_date_str:
                expiration_date = datetime.strptime(exp_date_str, '%Y-%m-%d')

        # Update batch with completion data
        batch.final_quantity = final_quantity
        batch.output_unit = output_unit
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        batch.is_perishable = is_perishable
        batch.shelf_life_days = shelf_life_days
        batch.expiration_date = expiration_date

        if output_type == 'ingredient':
            # Handle intermediate ingredient creation
            _create_intermediate_ingredient(batch, final_quantity, output_unit, expiration_date)
        else:
            # Handle product creation
            product_id = request.form.get('product_id')
            variant_id = request.form.get('variant_id')

            if not product_id or not variant_id:
                flash('Product and variant selection required', 'error')
                return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

            _create_product_output(batch, product_id, variant_id, final_quantity, output_unit, expiration_date, request.form)

        try:
            db.session.commit()
            flash(f'Batch {batch.label_code} completed successfully!', 'success')
            return redirect(url_for('batches.list_batches'))
        except Exception as commit_error:
            db.session.rollback()
            flash(f'Failed to complete batch due to database error: {str(commit_error)}', 'error')
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing batch {batch_id}: {str(e)}")
        flash(f'Error completing batch: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))


def _create_intermediate_ingredient(batch, final_quantity, output_unit, expiration_date):
    """Create intermediate ingredient from batch completion"""
    try:
        # Create or get inventory item for the intermediate ingredient
        ingredient_name = f"{batch.recipe.name} (Intermediate)"

        inventory_item = InventoryItem.query.filter_by(
            name=ingredient_name,
            organization_id=current_user.organization_id
        ).first()

        if not inventory_item:
            inventory_item = InventoryItem(
                name=ingredient_name,
                unit=output_unit,
                type='ingredient',  # Set the type properly
                intermediate=True,  # Mark as intermediate ingredient
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(inventory_item)
            db.session.flush()  # Ensure we get the ID

        # Process inventory adjustment to add the intermediate ingredient
        success = process_inventory_adjustment(
            item_id=inventory_item.id,
            quantity=final_quantity,
            change_type='finished_batch',
            unit=output_unit,
            notes=f'Batch {batch.label_code} completed',
            created_by=current_user.id,
            custom_expiration_date=expiration_date,
            item_type='ingredient'  # Ensure proper FIFO routing for intermediate ingredients
        )

        if not success:
            raise ValueError(f"Failed to add intermediate ingredient inventory")

        logger.info(f"Created intermediate ingredient: {ingredient_name}, quantity: {final_quantity} {output_unit}")

    except Exception as e:
        logger.error(f"Error creating intermediate ingredient: {str(e)}")
        raise


def _create_product_output(batch, product_id, variant_id, final_quantity, output_unit, expiration_date, form_data):
    """Create product SKUs from batch completion using centralized inventory adjustment"""
    try:
        # Get product and variant with proper organization scoping
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        variant = ProductVariant.query.filter_by(
            id=variant_id,
            product_id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product or not variant:
            raise ValueError("Invalid product or variant selection")

        # Calculate total ingredient cost for unit cost calculation
        total_ingredient_cost = 0

        # Add regular batch ingredients
        for ing in batch.batch_ingredients:
            total_ingredient_cost += (ing.quantity_used or 0) * (ing.cost_per_unit or 0)

        # Add extra ingredients
        for extra in batch.extra_ingredients:
            total_ingredient_cost += (extra.quantity_used or 0) * (extra.cost_per_unit or 0)

        # Calculate ingredient unit cost (cost per unit of final product)
        ingredient_unit_cost = total_ingredient_cost / final_quantity if final_quantity > 0 else 0

        logger.info(f"Batch {batch.label_code}: Total ingredient cost ${total_ingredient_cost:.2f}, Unit cost ${ingredient_unit_cost:.2f} per {output_unit}")

        # Process container allocations with cost calculation
        container_skus = _process_container_allocations(batch, product, variant, form_data, expiration_date, ingredient_unit_cost)

        # Calculate total product volume used in containers
        total_container_volume = 0
        for sku_info in container_skus:
            # Each container holds storage_amount * number of containers
            container_capacity = sku_info.get('container_capacity', 1)
            container_count = sku_info.get('quantity', 0)
            total_container_volume += container_capacity * container_count

        # Calculate bulk quantity (remaining after containers)
        bulk_quantity = max(0, final_quantity - total_container_volume)

        # Create bulk SKU if there's remaining quantity
        if bulk_quantity > 0:
            bulk_unit = output_unit
            if bulk_unit != product.base_unit:
                logger.warning(f"Bulk unit {bulk_unit} differs from product base unit {product.base_unit}")

            _create_bulk_sku(product, variant, bulk_quantity, bulk_unit, expiration_date, batch, ingredient_unit_cost)

        logger.info(f"Created product output for batch {batch.label_code}: {len(container_skus)} container SKUs, {bulk_quantity} {bulk_unit if bulk_quantity > 0 else ''} bulk")

    except Exception as e:
        logger.error(f"Error creating product output: {str(e)}")
        raise


def _process_container_allocations(batch, product, variant, form_data, expiration_date, ingredient_unit_cost):
    """Process container allocations and create SKUs"""
    container_skus = []

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
                    organization_id=current_user.organization_id
                ).first()

                if not container_item:
                    logger.error(f"Container with ID {container_id} not found for organization {current_user.organization_id}")
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
                container_sku = _create_container_sku(
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
                    'container_capacity': container_item.storage_amount or 1  # Volume per container
                })

                logger.info(f"Created container SKU for {final_quantity} x {container_item.name} containers")

            except Exception as e:
                logger.error(f"Error processing container {container_id}: {e}")
                import traceback
                logger.error(f"Container processing traceback: {traceback.format_exc()}")
                continue

    return container_skus


def _create_container_sku(product, variant, container_item, quantity, batch, expiration_date, ingredient_unit_cost, adjusted_container_cost):
    """Create or get existing container SKU using ProductService"""
    try:
        logger.info(f"Creating container SKU with container: {container_item.name}, quantity: {quantity}")

        # Create size label format: "[storage_amount] [storage_unit] [container_name]"
        # Example: "4 floz Admin 4oz Glass Jars"
        if container_item.storage_amount and container_item.storage_unit:
            size_label = f"{container_item.storage_amount} {container_item.storage_unit} {container_item.name}"
        else:
            size_label = f"1 unit {container_item.name}"

        # Calculate total cost per container unit
        # Cost = (ingredient cost per unit × container capacity) + adjusted container cost
        container_capacity = container_item.storage_amount or 1
        ingredient_cost_per_container = ingredient_unit_cost * container_capacity
        total_cost_per_container = ingredient_cost_per_container + adjusted_container_cost

        logger.info(f"Container cost breakdown: ${ingredient_cost_per_container:.2f} ingredients + ${adjusted_container_cost:.2f} container = ${total_cost_per_container:.2f} per container")

        # Use ProductService to get or create the SKU - this handles existing SKUs properly
        from ...services.product_service import ProductService
        product_sku = ProductService.get_or_create_sku(
            product_name=product.name,
            variant_name=variant.name,
            size_label=size_label,
            unit='count'  # Containers are always counted as individual units
        )

        # Add containers to inventory - quantity is number of containers
        success = process_inventory_adjustment(
            item_id=product_sku.inventory_item_id,
            quantity=quantity,  # Number of containers
            change_type='finished_batch',
            unit='count',  # Unit is count for containers
            notes=f'Batch {batch.label_code} completed - {quantity} containers of {size_label}',
            created_by=current_user.id,
            custom_expiration_date=expiration_date,
            cost_override=total_cost_per_container,  # Pass calculated cost per container
            item_type='product'  # Ensure proper FIFO routing
        )

        if not success:
            raise ValueError(f"Failed to add container inventory for {size_label}")

        # Calculate expiration date for batch output
        expiration_date = None
        is_perishable = False
        shelf_life_days = None

        # First check if batch has expiration settings
        if batch.is_perishable and batch.shelf_life_days:
            is_perishable = True
            shelf_life_days = batch.shelf_life_days
            # Use batch completion time for expiration calculation
            from ...blueprints.expiration.services import ExpirationService
            expiration_date = ExpirationService.calculate_expiration_date(
                batch.completed_at or batch.started_at, shelf_life_days
            )
        else:
            # Fall back to inventory item's master shelf life settings
            inventory_item = product_sku.inventory_item
            if inventory_item and inventory_item.is_perishable and inventory_item.shelf_life_days:
                is_perishable = True
                shelf_life_days = inventory_item.shelf_life_days
                from ...blueprints.expiration.services import ExpirationService
                expiration_date = ExpirationService.calculate_expiration_date(
                    batch.completed_at or batch.started_at, shelf_life_days
                )

        logger.info(f"Successfully created/updated container SKU: {product_sku.sku_code} with {quantity} containers at ${total_cost_per_container:.2f} per container")
        return product_sku

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

        # Add bulk quantity to inventory with calculated unit cost
        success = process_inventory_adjustment(
            item_id=bulk_sku.inventory_item_id,
            quantity=quantity,
            change_type='finished_batch',
            unit=unit,
            notes=f'Batch {batch.label_code} completed - bulk remainder',
            created_by=current_user.id,
            custom_expiration_date=expiration_date,
            cost_override=ingredient_unit_cost,  # Pass ingredient unit cost for bulk
            item_type='product'  # Ensure proper FIFO routing
        )

        if not success:
            raise ValueError(f"Failed to add bulk inventory for {quantity} {unit}")

        # Calculate expiration date for bulk output
        expiration_date = None
        is_perishable = False
        shelf_life_days = None

        # First check if batch has expiration settings
        if batch.is_perishable and batch.shelf_life_days:
            is_perishable = True
            shelf_life_days = batch.shelf_life_days
            # Use batch completion time for expiration calculation
            from ...blueprints.expiration.services import ExpirationService
            expiration_date = ExpirationService.calculate_expiration_date(
                batch.completed_at or batch.started_at, shelf_life_days
            )
        else:
            # Fall back to inventory item's master shelf life settings
            inventory_item = bulk_sku.inventory_item
            if inventory_item and inventory_item.is_perishable and inventory_item.shelf_life_days:
                is_perishable = True
                shelf_life_days = inventory_item.shelf_life_days
                from ...blueprints.expiration.services import ExpirationService
                expiration_date = ExpirationService.calculate_expiration_date(
                    batch.completed_at or batch.started_at, shelf_life_days
                )

        logger.info(f"Created/updated bulk SKU: {bulk_sku.sku_code} with {quantity} {unit} at ${ingredient_unit_cost:.2f} per {unit}")
        return bulk_sku

    except Exception as e:
        logger.error(f"Error creating bulk SKU: {str(e)}")
        raise