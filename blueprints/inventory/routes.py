from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session
from flask_login import login_required, current_user
from models import db, InventoryItem, Unit, IngredientCategory, InventoryHistory, User
from utils.unit_utils import get_global_unit_list
from utils.fifo_generator import get_change_type_prefix, int_to_base36
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
    from datetime import datetime
    return render_template('inventory/view.html',
                         abs=abs,
                         item=item,
                         history=history,
                         pagination=pagination,
                         units=get_global_unit_list(),
                         get_global_unit_list=get_global_unit_list,
                         get_ingredient_categories=IngredientCategory.query.order_by(IngredientCategory.name).all,
                         User=User,
                         InventoryHistory=InventoryHistory,
                         now=datetime.utcnow(),
                         get_change_type_prefix=get_change_type_prefix,
                         int_to_base36=int_to_base36)

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity', 0))
    unit = request.form.get('unit')
    item_type = request.form.get('type', 'ingredient')
    cost_per_unit = float(request.form.get('cost_per_unit', 0))
    low_stock_threshold = float(request.form.get('low_stock_threshold', 0))
    is_perishable = request.form.get('is_perishable') == 'on'
    expiration_date = None

    shelf_life_days = None
    if is_perishable:
        shelf_life_days = int(request.form.get('shelf_life_days', 0))
        if shelf_life_days > 0:
            from datetime import datetime, timedelta
            expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)

    # Handle container-specific fields
    storage_amount = None
    storage_unit = None
    if item_type == 'container':
        storage_amount = float(request.form.get('storage_amount', 0))
        storage_unit = request.form.get('storage_unit')

    item = InventoryItem(
        name=name,
        quantity=0,  # Start at 0, will be updated by history
        unit=unit,
        type=item_type,
        cost_per_unit=cost_per_unit,
        low_stock_threshold=low_stock_threshold,
        is_perishable=is_perishable,
        shelf_life_days=shelf_life_days,
        expiration_date=expiration_date,
        storage_amount=storage_amount,
        storage_unit=storage_unit
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
            quantity_used=0,  # Required field for FIFO tracking
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            expiration_date=expiration_date
        )
        db.session.add(history)
        item.quantity = quantity  # Update the current quantity

    db.session.commit()
    flash('Inventory item added successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
@login_required
def adjust_inventory(id):
    try:
        # Pre-validation check
        from services.inventory_adjustment import validate_inventory_fifo_sync
        is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(id)
        if not is_valid:
            flash(f'Pre-adjustment validation failed: {error_msg}', 'error')
            return redirect(url_for('inventory.view_inventory', id=id))

        change_type = request.form.get('change_type')
        input_quantity = float(request.form.get('quantity', 0))
        input_unit = request.form.get('input_unit')
        notes = request.form.get('notes', '')

        # Handle cost input for restocks (weighted average will be calculated in service)
        input_cost = request.form.get('cost_per_unit')
        cost_entry_type = request.form.get('cost_entry_type', 'no_change')

        restock_cost = None
        if input_cost and change_type == 'restock':
            cost_value = float(input_cost)
            if cost_entry_type == 'total':
                # Divide total cost by quantity to get per-unit cost
                restock_cost = cost_value / input_quantity if input_quantity > 0 else 0
            elif cost_entry_type == 'per_unit':
                restock_cost = cost_value

        # Use centralized adjustment service
        from services.inventory_adjustment import process_inventory_adjustment
        success = process_inventory_adjustment(
            item_id=id,
            quantity=input_quantity,
            change_type=change_type,
            unit=input_unit,
            notes=notes,
            created_by=current_user.id,
            cost_override=restock_cost  # Only pass cost for restocks, not overrides
        )

        if success:
            flash('Inventory adjusted successfully')
        else:
            flash('Error adjusting inventory', 'error')

    except ValueError as e:
        flash(f'Error: {str(e)}', 'error')
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')

    return redirect(url_for('inventory.view_inventory', id=id))



@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_inventory(id):
    item = InventoryItem.query.get_or_404(id)

    # Common fields for all types
    item.name = request.form.get('name')
    new_quantity = float(request.form.get('quantity'))

    # Handle expiration date if item is perishable
    is_perishable = request.form.get('is_perishable') == 'on'
    was_perishable = item.is_perishable
    item.is_perishable = is_perishable

    if is_perishable:
        shelf_life_days = int(request.form.get('shelf_life_days', 0))
        item.shelf_life_days = shelf_life_days
        from datetime import datetime, timedelta
        if shelf_life_days > 0:
            item.expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)
            # If item wasn't perishable before, update existing FIFO entries
            if not was_perishable:
                from blueprints.fifo.services import update_fifo_perishable_status
                update_fifo_perishable_status(item.id, shelf_life_days)

    # Handle recount if quantity changed
    if new_quantity != item.quantity:
        from blueprints.fifo.services import recount_fifo
        notes = "Manual quantity update via inventory edit"
        success = recount_fifo(item.id, new_quantity, notes, current_user.id)
        if not success:
            flash('Error updating quantity', 'error')
            return redirect(url_for('inventory.view_inventory', id=id))
        item.quantity = new_quantity  # Update main inventory quantity after successful FIFO adjustment

    # Handle cost override (only for manual cost changes from edit modal)
    new_cost = float(request.form.get('cost_per_unit', 0))
    if request.form.get('override_cost') and new_cost != item.cost_per_unit:
        # This is a true cost override - bypasses weighted average
        history = InventoryHistory(
            inventory_item_id=item.id,
            change_type='cost_override',
            quantity_change=0,
            unit_cost=new_cost,
            note=f'Cost manually overridden from {item.cost_per_unit} to {new_cost}',
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
        new_unit = request.form.get('unit')
        convert_inventory = request.form.get('convert_inventory_on_unit_change')
        old_unit = item.unit

        # Handle unit change with proper validation
        if new_unit != item.unit:
            if not convert_inventory:
                # Unit label change only - warn user but allow
                flash(f'Unit changed from {old_unit} to {new_unit}. Quantity ({item.quantity}) unchanged.', 'warning')
                item.unit = new_unit
            else:
                # Convert inventory quantity
                from services.conversion_wrapper import safe_convert
                old_quantity = item.quantity
                conversion = safe_convert(item.quantity, item.unit, new_unit, ingredient_id=item.id)
                if conversion['ok']:
                    item.quantity = conversion['result']['converted_value']
                    item.unit = new_unit

                    # Create history entry for the unit conversion
                    history = InventoryHistory(
                        inventory_item_id=item.id,
                        change_type='unit_conversion',
                        quantity_change=0,  # No net change in actual inventory
                        unit_cost=item.cost_per_unit,
                        note=f'Unit conversion: {old_quantity} {old_unit} → {item.quantity} {new_unit}',
                        created_by=current_user.id,
                        quantity_used=0
                    )
                    db.session.add(history)
                    flash(f'Inventory converted: {old_quantity} {old_unit} → {item.quantity} {new_unit}', 'success')
                else:
                    flash(f'Cannot convert {old_unit} to {new_unit}: {conversion["error"]}', 'error')
                    return redirect(url_for('inventory.view_inventory', id=id))
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

@inventory_bp.route('/archive/<int:id>')
@login_required
def archive_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    try:
        item.is_archived = True
        db.session.commit()
        flash('Inventory item archived successfully.')
    except Exception as e:
        db.session.rollback()
        flash(f'Error archiving item: {str(e)}', 'error')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/restore/<int:id>')
@login_required
def restore_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    try:
        item.is_archived = False
        db.session.commit()
        flash('Inventory item restored successfully.')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring item: {str(e)}', 'error')
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