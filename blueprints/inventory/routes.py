from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session
from flask_login import login_required, current_user
from models import db, InventoryItem, Unit, IngredientCategory, InventoryHistory, User
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
@inventory_bp.route('/set-columns', methods=['POST'])
@login_required
def set_column_visibility():
    columns = request.form.getlist('columns')
    session['inventory_columns'] = columns
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/view/<int:id>')
@login_required
def view_inventory(id):
    page = request.args.get('page', 1, type=int)
    per_page = 5
    item = InventoryItem.query.get_or_404(id)
    history_query = InventoryHistory.query.filter_by(inventory_item_id=id).order_by(InventoryHistory.timestamp.desc())
    pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items
    return render_template('inventory/view.html',
                         abs=abs,
                         item=item,
                         history=history,
                         pagination=pagination,
                         units=get_global_unit_list(),
                         get_global_unit_list=get_global_unit_list,
                         get_ingredient_categories=IngredientCategory.query.order_by(IngredientCategory.name).all,
                         User=User)

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
        quantity=0,  # Start at 0, will be updated by history
        unit=unit,
        type=item_type,
        cost_per_unit=cost_per_unit,
        low_stock_threshold=low_stock_threshold,
        is_perishable=is_perishable
    )
    db.session.add(item)
    db.session.flush()  # Get the ID without committing

    # Create initial history entry for FIFO tracking
    if quantity > 0:
        history = InventoryHistory(
            inventory_item_id=item.id,
            change_type='restock',
            quantity_change=quantity,
            remaining_quantity=quantity,  # For FIFO tracking
            unit_cost=cost_per_unit,
            note='Initial stock creation',
            created_by=current_user.id if current_user else None,
            quantity_used=0  # Required field for FIFO tracking
        )
        db.session.add(history)
        item.quantity = quantity  # Update the current quantity

    db.session.commit()
    flash('Inventory item added successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
@login_required
def adjust_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    change_type = request.form.get('change_type')
    quantity = float(request.form.get('quantity', 0))
    # If no cost provided, use existing item cost for restocks, None for other types
    input_cost = request.form.get('cost_per_unit')
    if input_cost:
        cost_per_unit = float(input_cost)
    else:
        cost_per_unit = item.cost_per_unit if change_type not in ['spoil', 'trash', 'recount'] else None
    notes = request.form.get('notes', '')

    # Calculate the quantity change
    if change_type == 'recount':
        qty_change = quantity - item.quantity
    elif change_type in ['spoil', 'trash']:
        qty_change = -abs(quantity)
    else:
        qty_change = quantity

    # For restocks and positive adjustments, remaining_quantity starts equal to the quantity added
    remaining = qty_change if qty_change > 0 else 0
    
    if qty_change < 0:
        success, deduction_plan = deduct_fifo(item.id, abs(qty_change), change_type, notes)
        if not success:
            flash('Insufficient stock for FIFO deduction', 'error')
            return redirect(url_for('inventory.view_inventory', id=id))

        # Execute the FIFO deduction plan
        for entry_id, deduction_amount, unit_cost in deduction_plan:
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type=change_type,
                quantity_change=-deduction_amount,
                source_fifo_id=entry_id,
                unit_cost=unit_cost,
                note=notes,
                created_by=current_user.id
            )
            db.session.add(history)

        item.quantity += qty_change
    else:
        history = InventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=qty_change,
            remaining_quantity=remaining,  # Track remaining quantity for FIFO
            unit_cost=cost_per_unit,
            note=notes,
            quantity_used=0,
            created_by=current_user.id
        )
        db.session.add(history)
        item.quantity += qty_change

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

@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_inventory(id):
    item = InventoryItem.query.get_or_404(id)

    # Common fields for all types
    item.name = request.form.get('name')
    new_quantity = float(request.form.get('quantity'))

    # Handle recount if quantity changed
    if request.form.get('change_type') == 'recount' and new_quantity != item.quantity:
        history = InventoryHistory(
            inventory_item_id=item.id,
            change_type='recount',
            quantity_change=new_quantity - item.quantity,
            created_by=current_user.id if current_user else None,
            quantity_used=0
        )
        db.session.add(history)
    item.quantity = new_quantity

    # Handle cost override
    new_cost = float(request.form.get('cost_per_unit', 0))
    if request.form.get('override_cost') and new_cost != item.cost_per_unit:
        history = InventoryHistory(
            inventory_item_id=item.id,
            change_type='cost_override',
            quantity_change=0,
            unit_cost=new_cost,
            note=f'Cost manually changed from {item.cost_per_unit} to {new_cost}',
            created_by=current_user.id,
            quantity_used=0
        )
        db.session.add(history)
        item.cost_per_unit = new_cost

    # Type-specific updates
    if item.type == 'container':
        item.storage_amount = float(request.form.get('storage_amount'))
        item.storage_unit = request.form.get('storage_unit')
    else:
        item.unit = request.form.get('unit')
        item.category_id = request.form.get('category_id', None)
        if not item.category_id:  # Custom category selected
            item.density = float(request.form.get('density', 1.0))
        else:
            category = IngredientCategory.query.get(item.category_id)
            if category and category.default_density:
                item.density = category.default_density
            else:
                item.density = None

    db.session.commit()
    flash(f'{item.type.title()} updated successfully.')
    return redirect(url_for('inventory.view_inventory', id=id))

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

def deduct_fifo(item_id, quantity, change_type, notes):
    """
    Deducts quantity from the oldest inventory entries using FIFO.

    Args:
        item_id (int): The ID of the inventory item.
        quantity (float): The quantity to deduct.
        change_type (str): The type of change (e.g., 'use', 'spoil').
        notes (str): Additional notes for the history.

    Returns:
        tuple: (success, deduction_plan)
            success (bool): True if deduction was successful, False otherwise.
            deduction_plan (list): A list of tuples, where each tuple contains:
                (history_entry_id, quantity_deducted, unit_cost)
    """

    deduction_plan = []
    total_deducted = 0

    # Get the oldest inventory history entries with remaining quantity
    fifo_entries = InventoryHistory.query.filter_by(inventory_item_id=item_id) \
        .filter(InventoryHistory.remaining_quantity > 0) \
        .order_by(InventoryHistory.timestamp.asc()).all()

    if not fifo_entries:
        return False, []  # Insufficient stock

    for entry in fifo_entries:
        if total_deducted >= quantity:
            break

        deduct_from_entry = min(quantity - total_deducted, entry.remaining_quantity)
        entry.remaining_quantity -= deduct_from_entry
        total_deducted += deduct_from_entry

        deduction_plan.append((entry.id, deduct_from_entry, entry.unit_cost))

    if total_deducted < quantity:
        # Restore remaining quantities to prevent partial deductions
        for entry_id, deducted_amount, _ in deduction_plan:
            entry = InventoryHistory.query.get(entry_id)
            entry.remaining_quantity += deducted_amount
        db.session.rollback()  # Rollback changes
        return False, []  # Insufficient stock

    db.session.commit()
    return True, deduction_plan