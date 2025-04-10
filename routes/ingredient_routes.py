from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models import db, InventoryUnit

from models import Ingredient

ingredients_bp = Blueprint('ingredients', __name__)

@ingredients_bp.route('/ingredients')
@login_required
def list_ingredients():
    ingredients = Ingredient.query.all()
    units = InventoryUnit.query.all()
    return render_template('ingredients.html', ingredients=ingredients, units=units)

@ingredients_bp.route('/ingredients/add', methods=['POST'])
@login_required
def add_ingredient():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    db.session.add(Ingredient(name=name, quantity=quantity, unit=unit))
    db.session.commit()
    flash('Ingredient added.')
    return redirect(url_for('ingredients.ingredient_list'))

@ingredients_bp.route('/ingredients/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    if request.method == 'POST':
        ing.quantity = float(request.form.get('quantity'))
        ing.unit = request.form.get('unit')
        db.session.commit()
        flash('Ingredient updated.')
        return redirect(url_for('ingredients.ingredient_list'))
    units = InventoryUnit.query.all()
    return render_template('update_ingredient.html', ing=ing, units=units)

@ingredients_bp.route('/ingredients/quick-add', methods=['POST'])
@login_required
def quick_add_ingredient():
    data = request.get_json()
    name = data.get('name')
    unit = data.get('unit')

    if not name or not unit:
        return jsonify({'error': 'Name and unit are required'}), 400

    try:
        # Check for existing ingredient
        existing = Ingredient.query.filter_by(name=name).first()
        if existing:
            session['preselect_ingredient_id'] = existing.id
            session['add_ingredient_line'] = True
            return jsonify({'redirect': request.referrer})

        # Create new ingredient with quantity 0 for placeholder
        ingredient = Ingredient(name=name, quantity=0.0, unit=unit)
        db.session.add(ingredient)
        db.session.commit()

        # Store in session for recipe form auto-population
        session['preselect_ingredient_id'] = ingredient.id
        session['add_ingredient_line'] = True

        return jsonify({'redirect': request.referrer})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@ingredients_bp.route('/ingredients/delete/<int:id>')
@login_required
def delete_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    db.session.delete(ing)
    db.session.commit()
    flash('Ingredient deleted.')
    return redirect(url_for('ingredients.ingredient_list'))