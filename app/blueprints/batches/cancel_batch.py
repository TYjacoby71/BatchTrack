from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, Batch, BatchIngredient, BatchContainer, ExtraBatchIngredient, ExtraBatchContainer, InventoryItem
from datetime import datetime
from ...utils import get_setting
from ...services.inventory_adjustment import process_inventory_adjustment

cancel_batch_bp = Blueprint('cancel_batch', __name__)

@cancel_batch_bp.route('/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    # Use scoped query to ensure user can only access their organization's batches
    batch = Batch.scoped().filter_by(id=batch_id).first_or_404()

    # Validate ownership - only the creator or same organization can cancel
    if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
        flash("You don't have permission to cancel this batch.", "error")
        return redirect(url_for('batches.list_batches'))

    if batch.status != 'in_progress':
        flash("Only in-progress batches can be cancelled.")
        return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

    try:
        # Fetch batch ingredients, containers, and extra ingredients
        batch_ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
        batch_containers = BatchContainer.query.filter_by(batch_id=batch.id).all()
        extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch.id).all()
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch.id).all()

        # Pre-validate FIFO sync for all ingredients that will be credited back
        from app.services.inventory_adjustment import validate_inventory_fifo_sync

        # Check all batch ingredients
        for batch_ingredient in batch_ingredients:
            is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(batch_ingredient.inventory_item_id)
            if not is_valid:
                flash(f'Cannot cancel batch - inventory sync error for {batch_ingredient.inventory_item.name}: {error_msg}', 'error')
                return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

        # Check all extra ingredients
        for extra_ingredient in extra_ingredients:
            is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(extra_ingredient.inventory_item_id)
            if not is_valid:
                flash(f'Cannot cancel batch - inventory sync error for {extra_ingredient.inventory_item.name}: {error_msg}', 'error')
                return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

        # Credit batch ingredients back to inventory using centralized service
        for batch_ing in batch_ingredients:
            ingredient = batch_ing.inventory_item
            if ingredient:
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=batch_ing.quantity_used,  # Use quantity_used instead of amount_used
                    change_type='refunded',
                    unit=batch_ing.unit,
                    notes=f"Refunded from cancelled batch {batch.label_code}",
                    batch_id=batch.id,
                    created_by=current_user.id
                )

        # Credit extra ingredients back to inventory using centralized service
        for extra_ing in extra_ingredients:
            ingredient = extra_ing.inventory_item
            if ingredient:
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=extra_ing.quantity_used,  # Use quantity_used instead of quantity
                    change_type='refunded',
                    unit=extra_ing.unit,
                    notes=f"Extra ingredient refunded from cancelled batch {batch.label_code}",
                    batch_id=batch.id,
                    created_by=current_user.id
                )

        # Credit regular containers back to inventory using centralized service
        for batch_container in batch_containers:
            container = batch_container.container
            if container:
                process_inventory_adjustment(
                    item_id=container.id,
                    quantity=batch_container.quantity_used,  # Positive for credit
                    change_type='refunded',
                    unit=container.unit,
                    notes=f"Container refunded from cancelled batch {batch.label_code}",
                    batch_id=batch.id,
                    created_by=current_user.id
                )

        # Credit extra containers back to inventory using centralized service
        for extra_container in extra_containers:
            container = extra_container.container
            if container:
                process_inventory_adjustment(
                    item_id=container.id,
                    quantity=extra_container.quantity_used,  # Positive for credit
                    change_type='refunded',
                    unit=container.unit,
                    notes=f"Extra container refunded from cancelled batch {batch.label_code}",
                    batch_id=batch.id,
                    created_by=current_user.id
                )

        # Update batch status
        batch.status = 'cancelled'
        batch.cancelled_at = datetime.utcnow()
        db.session.add(batch)
        db.session.commit()

        # Build restoration summary
        restoration_summary = []
        for batch_ing in batch_ingredients:
            ingredient = batch_ing.inventory_item
            if ingredient:
                restoration_summary.append(f"{batch_ing.quantity_used} {batch_ing.unit} of {ingredient.name}")

        for extra_ing in extra_ingredients:
            if extra_ing.inventory_item:
                restoration_summary.append(f"{extra_ing.quantity_used} {extra_ing.unit} of {extra_ing.inventory_item.name}")

        for batch_container in batch_containers:
            container = batch_container.container
            if container:
                restoration_summary.append(f"{batch_container.quantity_used} {container.unit} of {container.name}")

        for extra_container in extra_containers:
            container = extra_container.container
            if container:
                restoration_summary.append(f"{extra_container.quantity_used} {container.unit} of {container.name}")

        # Show appropriate message
        settings = get_setting('alerts', {})
        if settings.get('show_inventory_refund', True):
            restored_items = ", ".join(restoration_summary)
            flash(f"Batch cancelled. Restored items: {restored_items}", "success")
        else:
            flash("Batch cancelled successfully", "success")

        # Inventory restoration is handled by centralized service

    except Exception as e:
        db.session.rollback()
        flash(f"Error cancelling batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))
    return redirect(url_for('batches.list_batches'))