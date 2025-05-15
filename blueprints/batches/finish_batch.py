
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required
from models import Batch, ProductInventory, InventoryItem, db, BatchTimer
from datetime import datetime

finish_batch_bp = Blueprint('finish_batch', __name__)

@finish_batch_bp.route('/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)

    if not request.form.get('force'):
        active_timers = BatchTimer.query.filter_by(batch_id=batch.id, status='pending').all()
        if active_timers:
            flash("This batch has active timers. Complete timers or force finish.", "warning")
            return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

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
            batch.expiration_date = datetime.strptime(request.form.get('expiration_date'), '%Y-%m-%d')

        # Output-type specific logic
        if output_type == 'product':
            batch.product_id = request.form.get('product_id')
            batch.variant_label = request.form.get('variant_label')
            db.session.add(ProductInventory(
                product_id=batch.product_id,
                variant=batch.variant_id,
                unit=batch.output_unit,
                quantity=batch.final_quantity,
                batch_id=batch.id
            ))

        elif output_type == 'ingredient':
            total_cost = sum(
                (ing.amount_used or 0) * (ing.cost_per_unit or 0) for ing in batch.ingredients
            ) + sum(
                (c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers
            ) + sum(
                (e.quantity or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients
            ) + sum(
                (e.quantity_used or 0) * (e.cost_each or 0) for e in batch.extra_containers
            )
            unit_cost = total_cost / final_quantity if final_quantity > 0 else 0

            ingredient = InventoryItem.query.filter_by(
                name=batch.recipe.name, type='ingredient', intermediate=True
            ).first()

            if ingredient:  # update
                total_qty = ingredient.quantity + final_quantity
                ingredient.cost_per_unit = ((ingredient.quantity * ingredient.cost_per_unit) + 
                                            (final_quantity * unit_cost)) / total_qty
                ingredient.quantity += final_quantity
            else:  # create
                ingredient = InventoryItem(
                    name=batch.recipe.name,
                    type='ingredient',
                    intermediate=True,
                    quantity=final_quantity,
                    unit=output_unit,
                    cost_per_unit=unit_cost
                )
                db.session.add(ingredient)

        # Finalize
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        batch.inventory_credited = True

        db.session.commit()
        flash("✅ Batch completed successfully!", "success")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error completing batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))
