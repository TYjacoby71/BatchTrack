from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, InventoryItem, ProductInventory
from datetime import datetime
from sqlalchemy import extract
import uuid, os
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')

@batches_bp.route('/start_batch', methods=['POST'])
@login_required
def start_batch():
    data = request.get_json()
    recipe = Recipe.query.get_or_404(data['recipe_id'])
    scale = float(data['scale'])

    # Get current year and count of batches for this recipe this year
    current_year = datetime.now().year
    year_batches = Batch.query.filter(
        Batch.recipe_id == recipe.id,
        extract('year', Batch.timestamp) == current_year
    ).count()

    new_batch = Batch(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        scale=scale,
        notes=data.get('notes', ''),
        label_code=f"{recipe.label_prefix or 'BTH'}-{current_year}-{year_batches + 1:03d}",
        status='in_progress'
    )

    db.session.add(new_batch)
    db.session.commit()

    # Deduct inventory at start of batch
    ingredient_errors = []

    for assoc in recipe.recipe_ingredients:
        ingredient = assoc.inventory_item
        if not ingredient:
            continue

        required_amount = assoc.amount * scale

        if ingredient.unit != assoc.unit:
            ingredient_errors.append(f"Unit mismatch for {ingredient.name}")
            continue

        if ingredient.quantity < required_amount:
            ingredient_errors.append(f"Not enough {ingredient.name} in stock.")
        else:
            ingredient.quantity -= required_amount
            db.session.add(ingredient)

    if ingredient_errors:
        flash("Some ingredients were not deducted due to errors: " + ", ".join(ingredient_errors), "warning")
    else:
        flash("Batch started and inventory deducted.", "success")

    db.session.commit()
    return jsonify({'batch_id': new_batch.id})

@batches_bp.route('/columns', methods=['POST'])
@login_required
def set_column_visibility():
    columns = request.form.getlist('columns')
    session['visible_columns'] = columns
    flash('Column preferences updated')
    return redirect(url_for('batches.list_batches'))

@batches_bp.route('/')
@login_required
def list_batches():
    query = Batch.query.order_by(Batch.timestamp.desc())
    # Default columns to show if user has not set preference
    visible_columns = session.get('visible_columns', ['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])

    status = request.args.get('status')
    recipe_id = request.args.get('recipe_id')
    start = request.args.get('start')
    end = request.args.get('end')

    if status:
        query = query.filter_by(status=status)

    if recipe_id:
        query = query.filter_by(recipe_id=recipe_id)
    if start:
        query = query.filter(Batch.timestamp >= start)
    if end:
        query = query.filter(Batch.timestamp <= end)

    batches = query.all()
    all_recipes = Recipe.query.order_by(Recipe.name).all()
    return render_template('batches_list.html', batches=batches, all_recipes=all_recipes, visible_columns=visible_columns)

@batches_bp.route('/<batch_identifier>')
@login_required
def view_batch(batch_identifier):
    try:
        if batch_identifier.isdigit():
            batch = Batch.query.get_or_404(int(batch_identifier))
        else:
            batch = Batch.query.filter_by(label_code=batch_identifier).first_or_404()

        if batch.status == 'in_progress':
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))
        return render_template('view_batch.html', batch=batch)
    except Exception as e:
        app.logger.error(f'Error viewing batch {batch_identifier}: {str(e)}')
        flash('Error viewing batch. Please try again.')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/<int:batch_id>/update-notes', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    batch.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Batch notes updated.')

    # Redirect based on batch status
    if batch.status == 'in_progress':
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))
    return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

@batches_bp.route('/in-progress/<batch_identifier>')
@login_required
def view_batch_in_progress(batch_identifier):
    if not isinstance(batch_identifier, int):
        batch_identifier = int(batch_identifier)
    batch = Batch.query.get_or_404(batch_identifier)
    if batch.status != 'in_progress':
        flash('This batch is already completed.')
        return redirect(url_for('batches.list_batches'))
    recipe = Recipe.query.get_or_404(batch.recipe_id)
    # Get units for dropdown
    from utils.unit_utils import get_global_unit_list
    units = get_global_unit_list()
    
    # Build cost summary
    total_cost = 0
    ingredient_costs = []

    for assoc in recipe.recipe_ingredients:
        ingredient = assoc.inventory_item
        used_amount = assoc.amount * batch.scale
        cost_per_unit = getattr(ingredient, 'cost_per_unit', 0) or 0
        line_cost = round(used_amount * cost_per_unit, 2)
        total_cost += line_cost

        ingredient_costs.append({
            'name': ingredient.name,
            'unit': ingredient.unit,
            'used': used_amount,
            'cost_per_unit': cost_per_unit,
            'line_cost': line_cost
        })

    # Only pass product_quantity if it exists in the batch
    product_quantity = batch.product_quantity if hasattr(batch, 'product_quantity') else None
    # Only pass batch_cost if ingredients are used
    batch_cost = round(total_cost, 2) if ingredient_costs else None

    inventory_items = InventoryItem.query.all()
    return render_template('batch_in_progress.html',
                         batch=batch,
                         recipe=recipe,
                         units=units,
                         batch_cost=batch_cost,
                         product_quantity=product_quantity,
                         ingredient_costs=ingredient_costs,
                         inventory_items=inventory_items)

@batches_bp.route('/finish/<int:batch_id>', methods=['POST'])
@login_required
def finish_batch(batch_id, force=False):
    batch = Batch.query.get_or_404(batch_id)
    action = request.form.get('action')

    try:
        # Handle save action
        if action == "save":
            batch.notes = request.form.get("notes", "")
            batch.tags = request.form.get("tags", "")
            db.session.commit()
            flash("Changes saved successfully.")
            return redirect(url_for('batches.list_batches'))

        # Prevent redundant status changes
        if batch.status == "completed" and action == "finish":
            return redirect(url_for('batches.view_batch', batch_identifier=batch.id))
        elif batch.status == "failed" and action == "fail":
            return redirect(url_for('batches.view_batch', batch_identifier=batch.id))

        # Timer check unless forced
        if not force and action == "finish":
            active_timers = BatchTimer.query.filter_by(batch_id=batch.id, completed=False).all()
            if active_timers:
                flash("This batch has active timers. Complete timers or confirm finish.", "warning")
                return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

        # Update batch data
        batch.notes = request.form.get("notes", "")
        batch.tags = request.form.get("tags", "")
        batch.total_cost = batch.total_cost or 0

        # Set status based on action
        if action == "finish":
            batch.status = "completed"
            flash("✅ Batch marked as completed.")
        elif action == "fail":
            batch.status = "failed" 
            flash("⚠️ Batch marked as failed.")
        else:
            flash("Unknown action. Please try again.")
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

        db.session.commit()
        return redirect(url_for('batches.view_batch', batch_identifier=batch.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Error completing batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

@batches_bp.route('/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash('Batch cancelled successfully.')
    return redirect(url_for('batches.list_batches'))

@batches_bp.route('/finish-with-timers/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def confirm_finish_with_timers(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if request.method == 'POST':
        return redirect(url_for('batches.finish_batch_force', batch_id=batch.id))
    return render_template('confirm_finish_with_timers.html', batch=batch)

@batches_bp.route('/force-finish/<int:batch_id>')
@login_required
def force_finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)

    # Optional: Warn if no active timers exist
    if all(timer.completed for timer in batch.timers):
        flash("All timers are already completed. Use the normal Finish Batch button.", "info")
        return redirect(url_for('batches.view_batch_in_progress', batch_id=batch.id))

    # Mark batch as finished
    batch.status = 'finished'
    db.session.commit()

    flash("Batch marked complete. Timers ignored.", "warning")
    return redirect(url_for('batches.view_batch', batch_id=batch.id))

@batches_bp.route("/by_product/<int:product_id>/variant/<variant>/size/<size>/unit/<unit>")
@login_required
def view_batches_by_variant(product_id, variant, size, unit):
    """View FIFO-ordered batches for a specific product variant"""
    batches = ProductInventory.query.filter_by(
        product_id=product_id,
        variant_label=variant,
        size_label=size,
        unit=unit
    ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

    return render_template(
        "batches/by_variant.html",
        batches=batches,
        variant=variant,
        size=size,
        unit=unit
    )