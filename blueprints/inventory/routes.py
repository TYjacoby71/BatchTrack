
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models import db, InventoryItem, Unit, Container

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/containers')
@login_required
def list_containers():
    containers = Container.query.all()
    return render_template('containers/list.html', containers=containers)

@inventory_bp.route('/containers/add', methods=['GET', 'POST'])
@login_required
def add_container():
    if request.method == 'POST':
        container = Container(
            name=request.form.get('name'),
            storage_amount=float(request.form.get('storage_amount') or 0),
            storage_unit=request.form.get('storage_unit')
        )
        db.session.add(container)
        db.session.commit()
        flash('Container added successfully.')
        return redirect(url_for('inventory.list_containers'))
    return render_template('containers/edit.html')

@inventory_bp.route('/containers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_container(id):
    container = Container.query.get_or_404(id)
    if request.method == 'POST':
        container.name = request.form.get('name')
        container.storage_amount = float(request.form.get('storage_amount') or 0)
        container.storage_unit = request.form.get('storage_unit')
        db.session.commit()
        flash('Container updated successfully.')
        return redirect(url_for('inventory.list_containers'))
    return render_template('containers/edit.html', container=container)

@inventory_bp.route('/containers/delete/<int:id>')
@login_required
def delete_container(id):
    container = Container.query.get_or_404(id)
    db.session.delete(container)
    db.session.commit()
    flash('Container deleted successfully.')
    return redirect(url_for('inventory.list_containers'))

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
    from utils.unit_utils import get_global_unit_list
    item = InventoryItem.query.get_or_404(id)
    units = get_global_unit_list()
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
