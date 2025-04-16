
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required
from models import db, InventoryUnit

from models import Ingredient

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory')
@login_required
def list_inventory():
    ingredients = Ingredient.query.all()
    units = InventoryUnit.query.all()
    return render_template('inventory_list.html', ingredients=ingredients, units=units)

@inventory_bp.route('/inventory/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    item_type = request.form.get('type', 'ingredient')
    db.session.add(Ingredient(name=name, quantity=quantity, unit=unit, type=item_type))
    db.session.commit()
    flash('Inventory item added.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/inventory/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_inventory(id):
    ing = Ingredient.query.get_or_404(id)
    if request.method == 'POST':
        ing.name = request.form.get('name')
        ing.quantity = float(request.form.get('quantity'))
        ing.unit = request.form.get('unit')
        ing.cost_per_unit = float(request.form.get('cost_per_unit', 0.0))
        ing.type = request.form.get('type', 'ingredient')
        db.session.commit()
        flash('Inventory item updated successfully.', 'success')
        return redirect(url_for('inventory.list_inventory'))
    units = InventoryUnit.query.all()
    return render_template('edit_inventory.html', ing=ing, units=units)

@inventory_bp.route('/inventory/delete/<int:id>')
@login_required
def delete_inventory(id):
    ing = Ingredient.query.get_or_404(id)
    db.session.delete(ing)
    db.session.commit()
    flash('Inventory item deleted successfully.', 'success')
    return redirect(url_for('inventory.list_inventory'))
