from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required
from models import db, BatchTimer, InventoryItem, ProductInventory, Batch
from datetime import datetime

finish_batch_bp = Blueprint('finish_batch', __name__)

@finish_batch_bp.route('/<int:batch_id>/fail', methods=['POST'])
@login_required
def mark_batch_failed(batch_id):
    """Mark a batch as failed"""
    batch = Batch.query.get_or_404(batch_id)

    batch.status = 'failed'
    batch.failed_at = datetime.utcnow()
    batch.status_reason = request.form.get('reason', '')

    db.session.commit()
    flash("⚠️ Batch marked as failed. Inventory remains deducted.", "warning")
    return redirect(url_for('batches.list_batches'))

@finish_batch_bp.route('/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    """Complete a successful batch"""
    batch = Batch.query.get_or_404(batch_id)

    # Check active timers unless force flag is set
    if not request.form.get('force'):
        active_timers = BatchTimer.query.filter_by(
            batch_id=batch.id,
            status='pending'
        ).all()
        if active_timers:
            flash("This batch has active timers. Complete timers or force finish.", "warning")
            return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

    # Get completion details
    output_type = request.form.get('output_type')
    final_quantity = float(request.form.get('final_quantity', 0))
    output_unit = request.form.get('output_unit') or batch.yield_unit

    # Validate required fields
    if not all([output_type, final_quantity > 0]):
        flash("Output type, quantity and unit are required", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

    try:
        # Update batch details
        batch.batch_type = output_type
        batch.final_quantity = final_quantity
        batch.output_unit = output_unit
        batch.notes = request.form.get('notes')
        batch.tags = request.form.get('tags')

        if output_type == 'product':
            batch.product_id = request.form.get('product_id')
            batch.variant_label = request.form.get('variant_label')

            # Create product inventory record
            product_inv = ProductInventory(
                product_id=batch.product_id,
                variant=batch.variant_id,
                unit=batch.output_unit,
                quantity=batch.final_quantity,
                batch_id=batch.id
            )
            db.session.add(product_inv)

        elif output_type == 'ingredient':
            # Calculate total batch cost
            ingredient_cost = sum((ing.amount_used or 0) * (ing.cost_per_unit or 0) for ing in batch.ingredients)
            container_cost = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
            extra_costs = sum((e.quantity or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients)
            extra_cont_costs = sum((e.quantity_used or 0) * (e.cost_each or 0) for e in batch.extra_containers)

            total_cost = ingredient_cost + container_cost + extra_costs + extra_cont_costs
            unit_cost = total_cost / final_quantity if final_quantity > 0 else 0

            # Create/update intermediate ingredient
            ingredient = InventoryItem.query.filter_by(
                name=batch.recipe.name,
                type='ingredient',
                intermediate=True
            ).first() or InventoryItem(
                name=batch.recipe.name,
                type='ingredient',
                intermediate=True
            )

            if ingredient.id:  # Existing ingredient - update with weighted average cost
                total_quantity = ingredient.quantity + final_quantity
                ingredient.cost_per_unit = ((ingredient.quantity * ingredient.cost_per_unit) + 
                                          (final_quantity * unit_cost)) / total_quantity
                ingredient.quantity += final_quantity
            else:  # New ingredient
                ingredient.quantity = final_quantity
                ingredient.unit = output_unit
                ingredient.cost_per_unit = unit_cost
                db.session.add(ingredient)

        # Mark batch as completed
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        batch.inventory_credited = True

        db.session.commit()
        flash("✅ Batch completed successfully!", "success")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error completing batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch', batch_identifier=batch.id))