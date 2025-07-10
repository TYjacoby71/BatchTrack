from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, BatchTimer, InventoryItem, ProductSKU, Batch
from datetime import datetime
from ...blueprints.expiration.services import ExpirationService

finish_batch_bp = Blueprint('finish_batch', __name__)

@finish_batch_bp.route('/<int:batch_id>/fail', methods=['POST'])
@login_required
def mark_batch_failed(batch_id):
    """Mark a batch as failed"""
    print(f"DEBUG: mark_batch_failed called with batch_id: {batch_id}")
    print(f"DEBUG: Request method: {request.method}")
    print(f"DEBUG: Request form data: {dict(request.form)}")
    print(f"DEBUG: Current user: {current_user.username if current_user.is_authenticated else 'Anonymous'}")

    try:
        # Use scoped query to ensure user can only access their organization's batches
        batch = Batch.scoped().filter_by(id=batch_id).first_or_404()
        print(f"DEBUG: Found batch: {batch.label_code}, current status: {batch.status}")

        # Validate ownership - only the creator or same organization can modify
        if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
            flash("You don't have permission to modify this batch.", "error")
            return redirect(url_for('batches.list_batches'))

        batch.status = 'failed'
        batch.failed_at = datetime.utcnow()
        batch.status_reason = request.form.get('reason', '')

        db.session.commit()
        print(f"DEBUG: Successfully marked batch {batch.label_code} as failed by user {current_user.id}")

        flash("⚠️ Batch marked as failed. Inventory remains deducted.", "warning")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        print(f"DEBUG: Error in mark_batch_failed: {str(e)}")
        db.session.rollback()
        flash(f"Error marking batch as failed: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

@finish_batch_bp.route('/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    # Use scoped query to ensure user can only access their organization's batches
    batch = Batch.scoped().filter_by(id=batch_id).first_or_404()

    # Validate ownership - only the creator or same organization can modify
    if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
        flash("You don't have permission to modify this batch.", "error")
        return redirect(url_for('batches.list_batches'))

    if not request.form.get('force'):
        active_timers = BatchTimer.query.filter_by(batch_id=batch.id, status='pending').all()
        if active_timers:
            flash("This batch has active timers. Complete timers or force finish.", "warning")
            return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

    # Start a savepoint to ensure atomic operations
    savepoint = db.session.begin_nested()
    
    try:
        # Basic required fields
        output_type = request.form.get('output_type')
        final_quantity_raw = request.form.get('final_quantity', '').strip()
        output_unit = request.form.get('output_unit') or batch.yield_unit

        final_quantity = float(final_quantity_raw)
        if not output_type or final_quantity <= 0:
            raise ValueError("Missing or invalid output type or quantity")

        # Core batch updates
        batch.batch_type = output_type
        batch.final_quantity = final_quantity
        batch.output_unit = output_unit

        # Optional fields
        batch.notes = request.form.get('notes') or batch.notes
        batch.tags = request.form.get('tags') or batch.tags

        # Perishable logic
        batch.is_perishable = request.form.get('is_perishable') == 'on'
        if batch.is_perishable:
            shelf_life_days = request.form.get('shelf_life_days', type=int)
            if not shelf_life_days or shelf_life_days <= 0:
                raise ValueError("Shelf life days required for perishable items")
            batch.shelf_life_days = shelf_life_days
            # Set expiration date if perishable
            # Calculate expiration date if perishable (use completion time as base)
            batch.expiration_date = None
            if batch.is_perishable and shelf_life_days:
                batch.expiration_date = ExpirationService.calculate_expiration_date(
                    datetime.utcnow(), shelf_life_days
                )

        # Output-type specific logic - MUST NOT fail after this point
        if output_type == 'product':
            batch.product_id = request.form.get('product_id')
            batch.variant_id = request.form.get('variant_id')

            # Get container count overrides from form
            container_overrides = {}
            for key, value in request.form.items():
                if key.startswith('container_final_'):
                    container_id = int(key.replace('container_final_', ''))
                    container_overrides[container_id] = int(value)

            # For actual products, use the BatchService to handle all SKU creation and inventory
            if batch.product_id and batch.variant_id:
                from ...services.batch_service import BatchService
                
                success, inventory_entries, error_msg = BatchService.finalize_product_output(
                    batch, container_overrides, final_quantity
                )
                
                if not success:
                    raise Exception(error_msg or "Failed to finalize product output")

        elif output_type == 'ingredient':
            # For intermediate ingredients, use the BatchService to handle all logic
            from ...services.batch_service import BatchService
            
            success, error_msg = BatchService.finalize_intermediate_output(
                batch, final_quantity, output_unit
            )
            
            if not success:
                raise Exception(error_msg or "Failed to finalize intermediate output")

        # Only finalize batch status if ALL inventory operations succeeded
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        batch.inventory_credited = True

        # Commit the savepoint and main transaction
        savepoint.commit()
        db.session.commit()
        
        flash("✅ Batch completed successfully!", "success")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        # Rollback everything including batch status changes
        savepoint.rollback()
        db.session.rollback()
        
        # Log the error for debugging
        print(f"ERROR: Batch {batch.id} completion failed: {str(e)}")
        
        flash(f"❌ Error completing batch: {str(e)}. No changes were made.", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))