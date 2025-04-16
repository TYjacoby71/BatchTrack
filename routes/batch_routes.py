from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, Ingredient
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
        label_code=f"{recipe.label_prefix or 'BTH'}-{current_year}-{year_batches + 1:03d}"
    )

    db.session.add(new_batch)
    db.session.commit()

    # Deduct inventory at start of batch
    ingredient_errors = []

    for assoc in recipe.recipe_ingredients:
        ingredient = assoc.ingredient
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
        if status == 'in_progress':
            query = query.filter(Batch.total_cost.is_(None))
        elif status == 'completed':
            query = query.filter(Batch.total_cost.isnot(None))

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
        # Check if the identifier is a label code
        if not batch_identifier.isdigit():
            batch = Batch.query.filter_by(label_code=batch_identifier).first_or_404()
        else:
            batch = Batch.query.get_or_404(int(batch_identifier))

        if batch.total_cost is None:
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))
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

@batches_bp.route('/in-progress/<batch_identifier>')
@login_required
def view_batch_in_progress(batch_identifier):
    if not isinstance(batch_identifier, int):
        batch_identifier = int(batch_identifier)
    batch = Batch.query.get_or_404(batch_identifier)
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

@batches_bp.route('/finish/<int:batch_id>', methods=['POST'])
@login_required
def finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if batch.total_cost is not None:
        flash('This batch is already completed.')
        return redirect(url_for('batches.list_batches'))

    # Get and save output type
    output_type = request.form.get("output_type", "product")
    batch.mode = output_type

    # Calculate total cost from ingredient costs
    total_cost = 0
    for i in range(int(request.form.get('total_ingredients', 0))):
        amount = float(request.form.get(f'amount_{i}', 0))
        ingredient = Ingredient.query.filter_by(name=request.form.get(f'ingredient_{i}')).first()
        if ingredient:
            total_cost += amount * (ingredient.cost_per_unit or 0)

    batch.total_cost = total_cost
    db.session.commit()
    return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

@batches_bp.route('/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash('Batch cancelled successfully.')
    return redirect(url_for('batches.list_batches'))