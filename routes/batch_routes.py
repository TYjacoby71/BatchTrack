from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, Ingredient
from datetime import datetime
import uuid, os
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')

@batches_bp.route('/start_batch', methods=['POST'])
@login_required
def start_batch():
    data = request.get_json()
    recipe = Recipe.query.get_or_404(data['recipe_id'])
    
    new_batch = Batch(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        scale=data['scale'],
        notes=data.get('notes', ''),
        label_code=f"{recipe.label_prefix or 'BTH'}-{uuid.uuid4().hex[:8].upper()}"
    )
    
    db.session.add(new_batch)
    db.session.commit()
    
    return jsonify({'batch_id': new_batch.id})

@batches_bp.route('/')
@login_required
def list_batches():
    batches = Batch.query.order_by(Batch.timestamp.desc()).all()
    return render_template('batches_list.html', batches=batches)

@batches_bp.route('/<int:batch_id>')
@login_required
def view_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)
        if not batch.total_cost:
            return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))
        return render_template('view_batch.html', batch=batch)
    except Exception as e:
        flash(f'Error viewing batch: {str(e)}')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/update_notes/<int:batch_id>', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    batch.notes = request.form.get('notes', '')
    db.session.commit()
    return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

@batches_bp.route('/in-progress/<int:batch_id>')
@login_required
def view_batch_in_progress(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if batch.total_cost is not None:
        flash('This batch is already completed.')
        return redirect(url_for('batches.list_batches'))
    recipe = Recipe.query.get_or_404(batch.recipe_id)
    product_units = ProductUnit.query.all()

    # Build cost summary
    total_cost = 0
    ingredient_costs = []

    for assoc in recipe.recipe_ingredients:
        ingredient = assoc.ingredient
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
    
    return render_template('batch_in_progress.html',
                         batch=batch,
                         recipe=recipe,
                         product_units=product_units,
                         batch_cost=batch_cost,
                         product_quantity=product_quantity,
                         ingredient_costs=ingredient_costs)

@batches_bp.route('/<int:batch_id>/finish', methods=['POST'])
@login_required
def finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    recipe = Recipe.query.get_or_404(batch.recipe_id)
    scale = batch.scale

    total_ingredients = int(request.form.get('total_ingredients', 0))
    total_cost = 0.0

    for i in range(total_ingredients):
        name = request.form.get(f'ingredient_{i}')
        amount = float(request.form.get(f'amount_{i}', 0))
        unit = request.form.get(f'unit_{i}')
        ingredient = Ingredient.query.filter_by(name=name).first()

        if ingredient:
            used = amount
            ingredient.quantity -= used
            ingredient.quantity = round(max(ingredient.quantity, 0), 4)
            cost = ingredient.cost_per_unit or 0
            total_cost += cost * used

    db.session.commit()

    batch.total_cost = round(total_cost, 2)
    product_quantity = float(request.form.get('product_quantity', 1))
    batch.product_quantity = product_quantity
    batch.product_unit = request.form.get('product_unit')
    batch.tags = request.form.get('tags')
    batch.status = 'complete'
    batch.finished_on = datetime.utcnow()

    db.session.commit()
    flash("Batch completed and inventory deducted.", "success")
    return redirect(url_for('batch_view.view_batch', batch_id=batch.id))

@batches_bp.route('/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash('Batch cancelled successfully.')
    return redirect(url_for('batches.list_batches'))