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

        db.session.commit()
        flash(f'Batch {batch.label_code} completed successfully!', 'success')
        return redirect(url_for('batches.list_batches'))

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
                category='Intermediate',
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(inventory_item)
            db.session.flush()

        # Process inventory adjustment to add the intermediate ingredient
        process_inventory_adjustment(
            item_id=inventory_item.id,
            quantity=final_quantity,
            change_type='finished_batch',
            unit=output_unit,
            notes=f'Batch {batch.label_code} completed',
            created_by=current_user.id,
            custom_expiration_date=expiration_date
        )

        logger.info(f"Created intermediate ingredient: {ingredient_name}, quantity: {final_quantity} {output_unit}")

    except Exception as e:
        logger.error(f"Error creating intermediate ingredient: {str(e)}")
        raise


def _create_product_output(batch, product_id, variant_id, final_quantity, output_unit, expiration_date, form_data):
    """Create product SKUs from batch completion"""
    try:
        # Get product and variant
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

        # Process container allocations
        container_skus = _process_container_allocations(batch, product, variant, form_data, expiration_date)

        # Calculate bulk quantity (remaining after containers)
        total_container_quantity = sum(sku['quantity'] for sku in container_skus)
        bulk_quantity = max(0, final_quantity - total_container_quantity)

        # Create bulk SKU if there's remaining quantity
        if bulk_quantity > 0:
            _create_bulk_sku(product, variant, bulk_quantity, output_unit, expiration_date, batch)

        logger.info(f"Created product output for batch {batch.label_code}: {len(container_skus)} container SKUs, {bulk_quantity} bulk")

    except Exception as e:
        logger.error(f"Error creating product output: {str(e)}")
        raise


def _process_container_allocations(batch, product, variant, form_data, expiration_date):
    """Process container allocations and create SKUs"""
    container_skus = []

    # Process regular containers
    for container in batch.batch_containers:
        container_id = str(container.container_id)
        override_key = f"container_override_{container_id}"
        final_quantity = int(form_data.get(override_key, container.quantity_used))

        if final_quantity > 0:
            # Pass the container object and quantity separately
            container_sku = _create_container_sku(
                product=product, 
                variant=variant, 
                container_item=container.container,  # This is the InventoryItem object
                quantity=final_quantity,
                batch=batch,
                expiration_date=expiration_date
            )

            container_skus.append({
                'sku': container_sku,
                'quantity': final_quantity,
                'container_capacity': container.container.storage_amount or 1
            })

    # Process extra containers
    extra_container_ids = [k.replace('extra_container_', '') for k in form_data.keys() if k.startswith('extra_container_') and form_data[k]]

    for container_id in extra_container_ids:
        from ...models import InventoryItem
        container = InventoryItem.query.get(int(container_id))
        quantity = int(form_data.get(f'extra_container_{container_id}', 0))

        if container and quantity > 0:
            # Pass the container object and quantity separately
            container_sku = _create_container_sku(
                product=product,
                variant=variant,
                container_item=container,  # This is the InventoryItem object
                quantity=quantity,
                batch=batch,
                expiration_date=expiration_date
            )

            container_skus.append({
                'sku': container_sku,
                'quantity': quantity,
                'container_capacity': container.storage_amount or 1
            })

    return container_skus


def _create_container_sku(product, variant, container_item, quantity, batch, expiration_date):
    """Create a single container SKU"""
    try:
        # Create size label from container
        size_label = f"{container_item.storage_amount} {container_item.storage_unit}" if container_item.storage_amount else "1 unit"

        # Generate SKU code
        sku_code = f"{product.name[:3].upper()}-{variant.name[:3].upper()}-{container_item.name[:3].upper()}-{datetime.now().strftime('%m%d%H%M')}"

        # Create inventory item for this SKU
        inventory_item = InventoryItem(
            name=f"{product.name} - {variant.name} ({size_label})",
            unit=container_item.storage_unit or product.base_unit,
            category='Product',
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        db.session.add(inventory_item)
        db.session.flush()

        # Create ProductSKU
        product_sku = ProductSKU(
            product_id=product.id,
            variant_id=variant.id,
            sku_code=sku_code,
            size_label=size_label,
            unit_quantity=container_item.storage_amount or 1,
            unit_type=container_item.storage_unit or product.base_unit,
            inventory_item_id=inventory_item.id,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        db.session.add(product_sku)
        db.session.flush()

        # Add to inventory
        process_inventory_adjustment(
            item_id=inventory_item.id,
            quantity=quantity,  # Use the quantity passed to the function
            change_type='finished_batch',
            unit=inventory_item.unit,
            notes=f'Batch {batch.label_code} completed',
            created_by=current_user.id,
            custom_expiration_date=expiration_date
        )

        return product_sku

    except Exception as e:
        logger.error(f"Error creating container SKU: {str(e)}")
        raise


def _create_bulk_sku(product, variant, quantity, unit, expiration_date, batch):
    """Create or update bulk SKU for remaining quantity"""
    try:
        # Find or create bulk SKU
        bulk_sku = ProductSKU.query.filter_by(
            product_id=product.id,
            variant_id=variant.id,
            size_label='Bulk',
            organization_id=current_user.organization_id
        ).first()

        if not bulk_sku:
            # Create inventory item for bulk
            inventory_item = InventoryItem(
                name=f"{product.name} - {variant.name} (Bulk)",
                unit=unit,
                category='Product',
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(inventory_item)
            db.session.flush()

            # Create bulk SKU
            sku_code = f"{product.name[:3].upper()}-{variant.name[:3].upper()}-BULK-{datetime.now().strftime('%m%d%H%M')}"
            bulk_sku = ProductSKU(
                product_id=product.id,
                variant_id=variant.id,
                sku_code=sku_code,
                size_label='Bulk',
                unit_quantity=1,
                unit_type=unit,
                inventory_item_id=inventory_item.id,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(bulk_sku)
            db.session.flush()

        # Add bulk quantity to inventory
        process_inventory_adjustment(
            item_id=bulk_sku.inventory_item.id,
            quantity=quantity,
            change_type='finished_batch',
            unit=unit,
            notes=f'Batch {batch.label_code} completed - bulk quantity',
            created_by=current_user.id,
            custom_expiration_date=expiration_date
        )

        return bulk_sku

    except Exception as e:
        logger.error(f"Error creating bulk SKU: {str(e)}")
        raise