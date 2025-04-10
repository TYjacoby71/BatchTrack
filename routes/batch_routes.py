from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, Ingredient
from datetime import datetime
import uuid, os
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('/batches')
@login_required
def list_batches():
    batches = Batch.query.order_by(Batch.timestamp.desc()).all()
    return render_template('batches_list.html', batches=batches)

@batches_bp.route('/start', methods=['POST'])
@login_required
def start_batch():
    data = request.json
    recipe_id = data.get('recipe_id')
    scale = float(data.get('scale', 1.0))
    notes = data.get('notes', '')

    if not recipe_id or scale <= 0:
        return jsonify({"error": "Invalid input"}), 400

    recipe = Recipe.query.get_or_404(recipe_id)
    year = datetime.utcnow().year
    count = Batch.query.filter_by(recipe_name=recipe.name).count() + 1
    label_code = f"{recipe.label_prefix}-{year}{count:02d}"

    batch = Batch(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        scale=scale,
        label_code=label_code,
        notes=notes
    )
    db.session.add(batch)
    db.session.commit()
    return jsonify({
        "batch_id": batch.id,
        "redirect_url": url_for('batches.view_batch_in_progress', batch_id=batch.id)
    }), 201

@batches_bp.route('/batches/in-progress/<int:batch_id>')
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

    return render_template('batch_in_progress.html',
                         batch=batch,
                         recipe=recipe,
                         product_units=product_units,
                         batch_cost=round(total_cost, 2),
                         product_quantity=batch.product_quantity if hasattr(batch, 'product_quantity') else None,
                         ingredient_costs=ingredient_costs)

@batches_bp.route('/batches/in-progress/<int:batch_id>/notes', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    batch.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Notes updated successfully.')
    return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

@batches_bp.route('/batches/finish/<int:batch_id>', methods=['POST'])
@login_required
def finish_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)
        action = request.form.get('action')

        if action == 'fail':
            batch.total_cost = 0
            db.session.commit()
            flash("Batch marked as failed.")
            return redirect(url_for('home'))

        # Update actual ingredient usage
        total = int(request.form.get('total_ingredients', 0))
        used_ingredients = []
        total_cost = 0.0

        for i in range(total):
            name = request.form.get(f'ingredient_{i}')
            amount = float(request.form.get(f'amount_{i}', 0))
            unit = request.form.get(f'unit_{i}')

            ingredient = Ingredient.query.filter_by(name=name).first()
            if ingredient:
                if ingredient.quantity >= amount:
                    ingredient.quantity -= amount
                    ingredient_cost = float(ingredient.cost_per_unit or 0.0)
                    cost = round(amount * ingredient_cost, 2)
                    total_cost += cost
                    used_ingredients.append({
                        'name': name,
                        'amount': amount,
                        'unit': unit,
                        'cost': cost
                    })
                else:
                    flash(f'Insufficient quantity of {name}')
                    return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

        # Handle extra ingredients
        extra_ingredients = request.form.getlist('extra_ingredients[]')
        extra_amounts = request.form.getlist('extra_amounts[]')
        extra_units = request.form.getlist('extra_units[]')

        for i in range(len(extra_ingredients)):
            if extra_ingredients[i] and extra_amounts[i]:
                ingredient = Ingredient.query.filter_by(name=extra_ingredients[i]).first()
                amount = float(extra_amounts[i])
                if ingredient and ingredient.quantity >= amount:
                    ingredient.quantity -= amount
                    used_ingredients.append({
                        'name': extra_ingredients[i],
                        'amount': amount,
                        'unit': extra_units[i]
                    })
                else:
                    flash(f'Insufficient quantity of {extra_ingredients[i]}')
                    return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

        # Update batch notes with ingredient usage
        usage_notes = "Ingredients used:\n"
        for usage in used_ingredients:
            usage_notes += f"- {usage['name']}: {usage['amount']} {usage['unit']}\n"

        batch.notes = request.form.get('notes', '') + "\n" + usage_notes
        batch.tags = request.form.get('tags', '')

        # Calculate final cost
        batch.total_cost = total_cost if total_cost > 0 else (5.0 * batch.scale)

        # Handle product creation
        quantity = int(request.form.get('product_quantity', 1))
        if quantity <= 0:
            flash('Quantity must be greater than 0')
            return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

        product_unit = request.form.get('product_unit')
        if not product_unit:
            flash('Product unit is required')
            return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

        img_file = request.files.get('product_image')
        image_path = None
        if img_file and img_file.filename:
            filename = f"prod_{uuid.uuid4().hex}_{secure_filename(img_file.filename)}"
            save_path = os.path.join('static/product_images', filename)
            img_file.save(save_path)
            image_path = filename

        product = Product(
            batch_id=batch.id,
            name=batch.recipe_name,
            label_code=batch.label_code,
            image=image_path,
            expiration_date=datetime.utcnow().date(),
            quantity=quantity,
            unit=product_unit
        )
        db.session.add(product)
        db.session.commit()
        flash("Batch finished and product created.")
        return redirect(url_for('home'))
    except Exception as e:
        flash(f'Error finishing batch: {str(e)}')
        return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

@batches_bp.route('/batches/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash("Batch canceled and inventory restored.")
    return redirect(url_for('batches.list_batches'))