
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from models import db, InventoryItem, Unit, IngredientCategory, InventoryHistory
from utils.unit_utils import get_global_unit_list
from utils.unit_utils import get_global_unit_list

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/')
@login_required
def list_inventory():
    inventory_type = request.args.get('type')
    query = InventoryItem.query
    if inventory_type:
        query = query.filter_by(type=inventory_type)
    items = query.all()
    units = get_global_unit_list()
    return render_template('inventory_list.html', 
                         items=items, 
                         units=units, 
                         get_global_unit_list=get_global_unit_list)

@inventory_bp.route('/view/<int:id>')
@login_required
def view_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    history = InventoryHistory.query.filter_by(inventory_item_id=item.id).order_by(InventoryHistory.timestamp.desc()).all()
    return render_template('inventory/view.html', 
                         item=item,
                         history=history,
                         units=get_global_unit_list(),
                         get_global_unit_list=get_global_unit_list,
                         get_ingredient_categories=IngredientCategory.query.order_by(IngredientCategory.name).all)

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity', 0))
    unit = request.form.get('unit')
    item_type = request.form.get('type', 'ingredient')
    cost_per_unit = float(request.form.get('cost_per_unit', 0))
    low_stock_threshold = float(request.form.get('low_stock_threshold', 0))
    is_perishable = request.form.get('is_perishable', 'false') == 'true'

    item = InventoryItem(
        name=name,
        quantity=quantity,
        unit=unit,
        type=item_type,
        cost_per_unit=cost_per_unit,
        low_stock_threshold=low_stock_threshold,
        is_perishable=is_perishable
    )
    db.session.add(item)
    db.session.commit()
    flash('Inventory item added successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
@login_required
def adjust_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    change_type = request.form.get('change_type')
    quantity = float(request.form.get('quantity', 0))
    cost_per_unit = float(request.form.get('cost_per_unit')) if request.form.get('cost_per_unit') else None
    notes = request.form.get('notes', '')

    history = InventoryHistory(
        inventory_item_id=item.id,
        change_type=change_type,
        quantity_change=quantity if change_type != 'recount' else quantity - item.quantity,
        cost_per_unit=cost_per_unit,
        notes=notes
    )
    db.session.add(history)
    
    if change_type != 'recount':
        item.quantity += quantity
    else:
        item.quantity = quantity
        
    db.session.commit()
    flash('Inventory adjusted successfully')
    return redirect(url_for('inventory.view_inventory', id=id))

@inventory_bp.route('/update', methods=['POST'])
@login_required
def update_inventory():
    if request.is_json:
        # Handle AJAX inventory adjustment
        data = request.get_json()
        item_id = data.get('item_id')
        amount = float(data.get('amount', 0))
        notes = data.get('notes', '')

        item = InventoryItem.query.get(item_id)
        if item:
            # Create history entry
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type='adjustment',
                quantity_change=amount,
                cost_per_unit=item.cost_per_unit,
                notes=notes
            )
            db.session.add(history)

            # Update inventory
            item.quantity += amount
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Item not found'})

@inventory_bp.route('/edit/ingredient/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_ingredient(id):
    item = InventoryItem.query.get_or_404(id)
    if item.type != 'ingredient':
        abort(404)

    if request.method == 'POST':
        item.name = request.form.get('name')
        new_quantity = float(request.form.get('quantity'))
        if request.form.get('change_type') == 'recount' and new_quantity != item.quantity:
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type='recount',
                quantity_change=new_quantity - item.quantity,
                created_by=current_user.id if current_user else None,
                quantity_used=0  # Set default value for NOT NULL constraint
            )
            db.session.add(history)
        item.quantity = new_quantity
        item.unit = request.form.get('unit')
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        item.category_id = request.form.get('category_id', None)
        item.low_stock_threshold = float(request.form.get('low_stock_threshold', 0))
        item.is_perishable = request.form.get('is_perishable', 'false') == 'true'

        if not item.category_id:  # Custom category selected
            item.density = float(request.form.get('density', 1.0))
        else:
            category = IngredientCategory.query.get(item.category_id)
            if category and category.default_density:
                item.density = category.default_density
            else:
                item.density = None

        db.session.commit()
        flash('Ingredient updated successfully.')
        return redirect(url_for('inventory.view_inventory', id=id))

    return render_template('edit_ingredient.html', 
                         ing=item, 
                         get_ingredient_categories=IngredientCategory.query.order_by(IngredientCategory.name).all,
                         get_global_unit_list=get_global_unit_list)

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
    return render_template('edit_container.html', item=item, get_global_unit_list=get_global_unit_list)

@inventory_bp.route('/update_details/<int:id>', methods=['POST'])
@login_required
def update_details(id):
    item = InventoryItem.query.get_or_404(id)
    item.name = request.form.get('name')
    item.unit = request.form.get('unit')
    item.density = float(request.form.get('density')) if request.form.get('density') else None
    if item.type == 'ingredient':
        item.category_id = request.form.get('category_id') or None
    db.session.commit()
    flash('Item details updated successfully')
    return redirect(url_for('inventory.view_inventory', id=id))

@inventory_bp.route('/delete/<int:id>')
@login_required
def delete_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Inventory item deleted successfully.')
    return redirect(url_for('inventory.list_inventory'))
