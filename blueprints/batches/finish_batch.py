
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required
from models import db, BatchTimer, InventoryItem, ProductInventory, Batch
from datetime import datetime

finish_batch_bp = Blueprint('finish_batch', __name__)

@batches_bp.route('/<int:batch_id>/finish', methods=['POST'])
@login_required
def finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    return finish_batch_handler(batch)

def finish_batch_handler(batch, force=False):
    """Handle batch completion logic"""
    action = request.form.get('action', 'finish')
    
    # Handle fail action
    if action == 'fail':
        if batch.status != 'in_progress':
            flash("Only in-progress batches can be marked as failed.")
            return redirect(url_for('batches.view_batch', batch_identifier=batch.id))

        batch.status = 'failed'
        batch.completed_at = datetime.utcnow()
        db.session.commit()

        flash("Batch marked as failed. Inventory remains deducted.")
        return redirect(url_for('batches.list_batches'))

    # Handle finish action
    output_type = request.form.get('output_type')
    final_quantity = float(request.form.get('final_quantity', 0))
    output_unit = request.form.get('output_unit')
    notes = request.form.get('notes')

    # Update batch details
    batch.batch_type = output_type
    batch.final_quantity = final_quantity
    batch.output_unit = output_unit
    batch.notes = notes

    if output_type == 'product':
        batch.product_id = request.form.get('product_id')
        batch.variant_label = request.form.get('variant_label')

    try:
        # Verify batch can be finished
        if batch.status != 'in_progress':
            flash("Only in-progress batches can be finished.")
            return redirect(url_for('batches.view_batch', batch_identifier=batch.id))

        # Handle inventory crediting based on batch type
        if action == "finish":
            if batch.batch_type == 'ingredient':
                # Credit produced ingredient to inventory
                batch_unit_cost = batch.total_cost / batch.final_quantity if batch.final_quantity > 0 else 0
                ingredient = InventoryItem.query.filter_by(
                    name=batch.recipe.name, 
                    type='ingredient', 
                    intermediate=True
                ).first()
                
                if not ingredient:
                    ingredient = InventoryItem(
                        name=batch.recipe.name,
                        quantity=batch.final_quantity,
                        unit=batch.output_unit,
                        type='ingredient',
                        intermediate=True,
                        cost_per_unit=batch_unit_cost
                    )
                else:
                    total_old_cost = ingredient.quantity * ingredient.cost_per_unit
                    total_new_cost = batch.final_quantity * batch_unit_cost
                    total_quantity = ingredient.quantity + batch.final_quantity

                    if total_quantity > 0:
                        weighted_avg_cost = (total_old_cost + total_new_cost) / total_quantity
                        ingredient.cost_per_unit = weighted_avg_cost
                    ingredient.quantity += batch.final_quantity

                db.session.add(ingredient)
                batch.inventory_credited = True

            elif batch.batch_type == 'product':
                product_inv = ProductInventory(
                    product_id=batch.product_id,
                    variant=batch.variant_id,
                    unit=batch.output_unit,
                    quantity=batch.final_quantity,
                    batch_id=batch.id
                )
                db.session.add(product_inv)
                batch.inventory_credited = True

            # Timer check unless forced
            if not force:
                active_timers = BatchTimer.query.filter_by(
                    batch_id=batch.id, 
                    completed=False
                ).all()
                if active_timers:
                    flash("This batch has active timers. Complete timers or confirm finish.", "warning")
                    return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

            # Update batch completion status
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()

        # Save final batch data
        batch.notes = request.form.get("notes", batch.notes)
        batch.tags = request.form.get("tags", batch.tags)
        batch.completed_at = datetime.utcnow()

        # Set status based on action
        if action == "finish":
            batch.status = "completed"
            flash("✅ Batch marked as completed.")
        elif action == "fail":
            batch.status = "failed"
            flash("⚠️ Batch marked as failed.")

        db.session.commit()
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error completing batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))
