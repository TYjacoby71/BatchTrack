
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

@inventory_bp.route('/')
@login_required
def list_inventory():
    items = InventoryItem.query.all()
    units = Unit.query.order_by(Unit.type, Unit.is_custom, Unit.name).all()
    return render_template('inventory_list.html', items=items, units=units)

@inventory_bp.route('/delete/<int:id>')
@login_required
def delete_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Inventory item deleted successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.quantity = float(request.form.get('quantity'))
        item.unit = request.form.get('unit')
        item.type = request.form.get('type')
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        db.session.commit()
        flash('Inventory item updated successfully.')
        return redirect(url_for('inventory.list_inventory'))
    return render_template('inventory/edit.html', item=item)
