
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryItem
from utils.unit_utils import get_global_unit_list

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory')
@login_required
def list_inventory():
    inventory_type = request.args.get('type')
    query = InventoryItem.query
    if inventory_type:
        query = query.filter_by(type=inventory_type)
    items = query.all()
    units = get_global_unit_list()
    return render_template('inventory_list.html', items=items, units=units)

@inventory_bp.route('/inventory/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity', 0))
    unit = request.form.get('unit')
    item_type = request.form.get('type', 'ingredient')
    item = InventoryItem(name=name, quantity=quantity, unit=unit, type=item_type)
    db.session.add(item)
    db.session.commit()
    flash('Inventory item added successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/inventory/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.quantity = float(request.form.get('quantity'))
        item.unit = request.form.get('unit')
        item.type = request.form.get('type')
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        item.low_stock_threshold = float(request.form.get('low_stock_threshold', 0))
        item.is_perishable = request.form.get('is_perishable', 'false') == 'true'
        db.session.commit()
        flash('Inventory item updated successfully.')
        return redirect(url_for('inventory.list_inventory'))
    return render_template('inventory/edit.html', item=item)

@inventory_bp.route('/inventory/delete/<int:id>')
@login_required
def delete_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Inventory item deleted successfully.')
    return redirect(url_for('inventory.list_inventory'))
