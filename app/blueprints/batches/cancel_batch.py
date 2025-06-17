
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
    batch = Batch.query.get_or_404(batch_id)

    if batch.status != 'in_progress':
        flash("Only in-progress batches can be cancelled.")
        return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

    try:
        # Fetch batch ingredients, containers, and extra ingredients
        batch_ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
        batch_containers = BatchContainer.query.filter_by(batch_id=batch.id).all()
        extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch.id).all()
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch.id).all()

        # Credit batch ingredients back to inventory using centralized service
        for batch_ing in batch_ingredients:
            ingredient = batch_ing.ingredient
            if ingredient:
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=batch_ing.amount_used,  # Positive for credit
                    change_type='refunded',
                    unit=batch_ing.unit,
                    notes=f"Refunded from cancelled batch {batch.label_code}",
                    batch_id=batch.id,
                    created_by=current_user.id
                )

        # Credit extra ingredients back to inventory using centralized service
        for extra_ing in extra_ingredients:
            ingredient = extra_ing.ingredient
            if ingredient:
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=extra_ing.quantity,  # Positive for credit
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
            ingredient = InventoryItem.query.get(batch_ing.ingredient_id)
            if ingredient:
                restoration_summary.append(f"{batch_ing.amount_used} {batch_ing.unit} of {ingredient.name}")

        for extra_ing in extra_ingredients:
            if extra_ing.ingredient:
                restoration_summary.append(f"{extra_ing.quantity} {extra_ing.unit} of {extra_ing.ingredient.name}")

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
