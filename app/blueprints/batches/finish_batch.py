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
    """Create intermediate ingredient from batch completion using centralized batch service"""
    try:
        from app.services.batch_service import BatchService
        
        success, error_message = BatchService.finalize_intermediate_output(
            batch, final_quantity, output_unit
        )
        
        if not success:
            raise ValueError(f"Failed to create intermediate ingredient: {error_message}")
            
        logger.info(f"Created intermediate ingredient for batch {batch.label_code}: {final_quantity} {output_unit}")

    except Exception as e:
        logger.error(f"Error creating intermediate ingredient: {str(e)}")
        raise


def _create_product_output(batch, product_id, variant_id, final_quantity, output_unit, expiration_date, form_data):
    """Create product SKUs from batch completion using centralized batch service"""
    try:
        from app.services.batch_service import BatchService
        
        # Store product and variant IDs in batch for batch service
        batch.product_id = product_id
        batch.variant_id = variant_id
        
        # Parse container overrides from form data
        container_overrides = {}
        for key, value in form_data.items():
            if key.startswith('container_final_'):
                container_id = key.replace('container_final_', '')
                try:
                    container_overrides[int(container_id)] = int(value)
                except (ValueError, TypeError):
                    continue
        
        success, inventory_entries, error_message = BatchService.finalize_product_output(
            batch, container_overrides, final_quantity
        )
        
        if not success:
            raise ValueError(f"Failed to create product output: {error_message}")
            
        logger.info(f"Created product output for batch {batch.label_code}: {len(inventory_entries)} inventory entries")

    except Exception as e:
        logger.error(f"Error creating product output: {str(e)}")
        raise


# Helper functions removed - now handled by centralized BatchService