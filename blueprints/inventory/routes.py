
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryItem, Unit

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    type = request.form.get('type')
    cost_per_unit = float(request.form.get('cost_per_unit', 0))
    
    item = InventoryItem(name=name, quantity=quantity, unit=unit, type=type, cost_per_unit=cost_per_unit)
    db.session.add(item)
    db.session.commit()
    flash('Inventory item added successfully.')
    return redirect(url_for('inventory.list_inventory'))

from utils.unit_utils import get_global_unit_list

@inventory_bp.route('/')
@login_required
def list_inventory():
    items = InventoryItem.query.all()
    units = Unit.query.all()
    return render_template('inventory_list.html', 
                         items=items,
                         units=units,
                         get_global_unit_list=get_global_unit_list)

@inventory_bp.route('/delete/<int:id>')
@login_required
def delete_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Inventory item deleted successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/edit/ingredient/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_ingredient(id):
    item = InventoryItem.query.get_or_404(id)
    if item.type != 'ingredient':
        abort(404)
    
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.quantity = float(request.form.get('quantity'))
        item.unit = request.form.get('unit')
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        
        # Update category density
        if item.category:
            item.category.default_density = float(request.form.get('default_density', 1.0))
        db.session.commit()
        flash('Ingredient updated successfully.')
        return redirect(url_for('inventory.list_inventory'))
    return render_template('edit_ingredient.html', item=item)

@inventory_bp.route('/edit/container/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_container(id):
    item = InventoryItem.query.get_or_404(id)
    if item.type != 'container':
        abort(404)
    
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.storage_amount = float(request.form.get('storage_amount'))
        item.storage_unit = request.form.get('storage_unit')
        item.quantity = float(request.form.get('quantity'))
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        db.session.commit()
        flash('Container updated successfully.')
        return redirect(url_for('inventory.list_inventory'))
    return render_template('edit_container.html', item=item)
