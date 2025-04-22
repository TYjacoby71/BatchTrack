
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryItem, Unit

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/')
@login_required
def list_inventory():
    items = InventoryItem.query.all()
    return render_template('inventory/list.html', items=items)

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
