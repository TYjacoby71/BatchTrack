from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from ...models import db, InventoryItem, Unit, IngredientCategory, InventoryHistory, User
from ...utils.unit_utils import get_global_unit_list
from ...utils.fifo_generator import get_change_type_prefix, int_to_base36

# Import the blueprint from __init__.py instead of creating a new one
from . import inventory_bp

@inventory_bp.route('/')
@login_required
def list_inventory():
    inventory_type = request.args.get('type')
    query = InventoryItem.query
    if inventory_type:
        query = query.filter_by(type=inventory_type)
    inventory_items = query.all()
    units = get_global_unit_list()
    categories = IngredientCategory.query.all()
    total_value = sum(item.quantity * item.cost_per_unit for item in inventory_items)

    # Calculate freshness and expired quantities for each item
    from ...blueprints.expiration.services import ExpirationService
    from datetime import datetime
    from sqlalchemy import and_
    
    for item in inventory_items:
        item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)
        
        # Calculate expired quantity
        if item.is_perishable:
            today = datetime.now().date()
            expired_entries = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == item.id,
                    InventoryHistory.remaining_quantity > 0,
                    InventoryHistory.expiration_date != None,
                    InventoryHistory.expiration_date < today
                )
            ).all()
            item.expired_quantity = sum(entry.remaining_quantity for entry in expired_entries)
            item.available_quantity = item.quantity - item.expired_quantity
        else:
            item.expired_quantity = 0
            item.available_quantity = item.quantity

    return render_template('inventory_list.html', 
                         inventory_items=inventory_items,
                         items=inventory_items,  # Template expects 'items'
                         categories=categories,
                         total_value=total_value,
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
    fifo_filter = request.args.get('fifo') == 'true'

    item = InventoryItem.query.get_or_404(id)
    history_query = InventoryHistory.query.filter_by(inventory_item_id=id)

    # Apply FIFO filter at database level if requested
    if fifo_filter:
        history_query = history_query.filter(InventoryHistory.remaining_quantity > 0)

    history_query = history_query.order_by(InventoryHistory.timestamp.desc())
    pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items

    from datetime import datetime
    
    # Get expired FIFO entries for display
    from sqlalchemy import and_
    expired_entries = []
    expired_total = 0
    if item.is_perishable:
        today = datetime.now().date()
        expired_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today
            )
        ).order_by(InventoryHistory.expiration_date.asc()).all()
        expired_total = sum(entry.remaining_quantity for entry in expired_entries)
    return render_template('inventory/view.html',
                         abs=abs,
                         item=item,
                         history=history,
                         pagination=pagination,
                         expired_entries=expired_entries,
                         expired_total=expired_total,
                         units=get_global_unit_list(),
                         get_global_unit_list=get_global_unit_list,
                         get_ingredient_categories=IngredientCategory.query.order_by(IngredientCategory.name).all,
                         User=User,
                         InventoryHistory=InventoryHistory,
                         now=datetime.utcnow(),
                         get_change_type_prefix=get_change_type_prefix,
                         int_to_base36=int_to_base36,
                         fifo_filter=fifo_filter)

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')

    # Check for duplicate name first
    existing_item = InventoryItem.query.filter_by(name=name).first()
    if existing_item:
        flash(f'An item with the name "{name}" already exists. Please choose a different name.', 'error')
        return redirect(url_for('inventory.list_inventory'))

    try:
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

        # Handle container-specific fields and unit assignment
        storage_amount = None
        storage_unit = None
        if item_type == 'container':
            storage_amount = float(request.form.get('storage_amount', 0))
            storage_unit = request.form.get('storage_unit')
            # For containers, ensure unit is set to empty string and history uses 'count'
            unit = ''  # Containers don't have a unit on the item itself
            history_unit = 'count'  # But history entries use 'count'
        else:
            # For ingredients, use the provided unit for both item and history
            history_unit = unit

        # Debug: ensure history_unit is set correctly
        print(f"DEBUG: item_type={item_type}, unit={unit}, history_unit={history_unit}")

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
            storage_unit=storage_unit,
            organization_id=current_user.organization_id
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
                unit=history_unit,  # Use the correct unit for history
                unit_cost=cost_per_unit,
                note='Initial stock creation',
                created_by=current_user.id if current_user else None,
                quantity_used=0.0,  # Restocks don't consume inventory - always 0
                is_perishable=is_perishable,
                shelf_life_days=shelf_life_days,
                expiration_date=expiration_date,
                organization_id=current_user.organization_id
            )
            db.session.add(history)
            item.quantity = quantity  # Update the current quantity

        db.session.commit()
        flash('Inventory item added successfully.')
        return redirect(url_for('inventory.list_inventory'))

    except ValueError as e:
        print(f"DEBUG: ValueError in add_inventory: {str(e)}")
        db.session.rollback()
        flash(f'Invalid input values: {str(e)}', 'error')
        return redirect(url_for('inventory.list_inventory'))
    except ImportError as e:
        print(f"DEBUG: ImportError in add_inventory: {str(e)}")
        db.session.rollback()
        flash(f'Import error: {str(e)}', 'error')
    except Exception as e:
        print(f"DEBUG: Unexpected error in add_inventory: {str(e)}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f'Error adding inventory item: {str(e)}', 'error')
        return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
@login_required
def adjust_inventory(id):
    try:
        # Get the item first
        item = InventoryItem.query.get_or_404(id)

        # Check if this item has no history - this indicates it needs FIFO initialization
        history_count = InventoryHistory.query.filter_by(inventory_item_id=id).count()

        change_type = request.form.get('change_type')
        input_quantity = float(request.form.get('quantity', 0))
        input_unit = request.form.get('input_unit')

        # For containers, always use 'count' as the unit
        if item.type == 'container':
            input_unit = 'count'

        input_unit = request.form.get('input_unit', item.unit)
        notes = request.form.get('notes', '')
        cost_entry_type = request.form.get('cost_entry_type', 'no_change')
        cost_per_unit_input = request.form.get('cost_per_unit')

        # Handle custom shelf life override
        override_expiration = request.form.get('override_expiration') == 'on'
        custom_expiration_date = None
        if override_expiration and change_type == 'restock':
            custom_shelf_life_str = request.form.get('custom_shelf_life_days')
            if custom_shelf_life_str:
                try:
                    custom_shelf_life = int(custom_shelf_life_str)
                    if custom_shelf_life > 0:
                        from app.blueprints.expiration.services import ExpirationService
                        custom_expiration_date = ExpirationService.calculate_expiration_date(
                            datetime.utcnow(), custom_shelf_life
                        )
                except (ValueError, TypeError):
                    flash('Invalid shelf life value', 'error')
                    return redirect(url_for('inventory.view_inventory', id=id))

        # Calculate restock cost based on entry type
        restock_cost = None
        if cost_entry_type == 'per_unit' and cost_per_unit_input:
            restock_cost = float(cost_per_unit_input)
        elif cost_entry_type == 'total' and cost_per_unit_input:
            total_cost = float(cost_per_unit_input)
            restock_cost = total_cost / input_quantity

        # Special case: FIFO initialization for items with no history
        if history_count == 0 and change_type == 'restock' and input_quantity > 0:
            # This is essentially the same as initial stock creation
            # Set the proper unit for history based on item type
            if item.type == 'container':
                history_unit = 'count'
            else:
                history_unit = item.unit or input_unit

            # Create initial FIFO entry directly (mimics add_inventory route)
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type='restock',
                quantity_change=input_quantity,
                remaining_quantity=input_quantity,  # For FIFO tracking
                unit=history_unit,
                unit_cost=restock_cost or item.cost_per_unit,
                note=notes or 'Initial stock creation via adjustment modal',
                created_by=current_user.id,
                quantity_used=0.0,  # Restocks don't consume inventory - always 0
                is_perishable=item.is_perishable,
                shelf_life_days=item.shelf_life_days,
                expiration_date=item.expiration_date
            )
            db.session.add(history)

            # Update inventory quantity
            item.quantity = input_quantity

            # Update cost if provided
            if restock_cost:
                item.cost_per_unit = restock_cost

            db.session.commit()
            flash('Initial inventory created successfully')

        else:
            # Pre-validation check for existing items
            from app.services.inventory_adjustment import validate_inventory_fifo_sync
            is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(id)
            if not is_valid:
                flash(f'Pre-adjustment validation failed: {error_msg}', 'error')
                return redirect(url_for('inventory.view_inventory', id=id))

            # Use centralized adjustment service for regular adjustments
            from app.services.inventory_adjustment import process_inventory_adjustment
            # Get custom shelf life for tracking
            quantity = input_quantity
            unit = input_unit
            cost_override = restock_cost

            custom_shelf_life = None
            if override_expiration:
                custom_shelf_life_str = request.form.get('custom_shelf_life_days')
                if custom_shelf_life_str:
                    try:
                        custom_shelf_life = int(custom_shelf_life_str)
                    except (ValueError, TypeError):
                        pass

            success = process_inventory_adjustment(
                item_id=id,
                quantity=quantity,
                change_type=change_type,
                unit=unit,
                notes=notes,
                created_by=current_user.id,
                cost_override=cost_override,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life
            )

            if success:
                flash('Inventory adjusted successfully')
            else:
                flash('Error adjusting inventory', 'error')

    except ValueError as e:
        print(f"DEBUG: ValueError in adjust_inventory: {str(e)}")
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    except ImportError as e:
        print(f"DEBUG: ImportError in adjust_inventory: {str(e)}")
        db.session.rollback()
        flash(f'Import error: {str(e)}', 'error')
    except Exception as e:
        print(f"DEBUG: Unexpected error in adjust_inventory: {str(e)}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f'Unexpected error: {str(e)}', 'error')

    return redirect(url_for('inventory.view_inventory', id=id))



@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_inventory(id):
    item = InventoryItem.query.get_or_404(id)

    # Handle unit changes with conversion confirmation
    if item.type != 'container':
        new_unit = request.form.get('unit')
        if new_unit != item.unit:
            # Check if item has any history entries
            history_count = InventoryHistory.query.filter_by(inventory_item_id=id).count()
            if history_count > 0:
                # Check if user confirmed the unit change
                confirm_unit_change = request.form.get('confirm_unit_change') == 'true'
                convert_inventory = request.form.get('convert_inventory') == 'true'

                if not confirm_unit_change:
                    # User hasn't confirmed - show them the options
                    flash(f'Unit change requires confirmation. Item has {history_count} transaction history entries. History will remain unchanged in original units.', 'warning')
                    session['pending_unit_change'] = {
                        'item_id': id,
                        'old_unit': item.unit,
                        'new_unit': new_unit,
                        'current_quantity': item.quantity
                    }
                    return redirect(url_for('inventory.view_inventory', id=id))
                else:
                    # User confirmed - proceed with unit change
                    if convert_inventory and item.quantity > 0:
                        # Try to convert existing inventory to new unit
                        try:
                            from app.services.unit_conversion import convert_unit
                            converted_quantity = convert_unit(item.quantity, item.unit, new_unit, item.density)
                            item.quantity = converted_quantity

                            # Log this conversion
                            history = InventoryHistory(
                                inventory_item_id=item.id,
                                change_type='unit_conversion',
                                quantity_change=0,  # No actual quantity change, just unit change
                                unit=new_unit,  # Record in the new unit
                                note=f'Unit converted from {item.unit} to {new_unit}. Quantity adjusted from {request.form.get("original_quantity", item.quantity)} {item.unit} to {converted_quantity} {new_unit}',
                                created_by=current_user.id,
                                quantity_used=0.0  # Unit conversions don't consume inventory - always 0
                            )
                            db.session.add(history)
                            flash(f'Unit changed and inventory converted: {item.quantity} {item.unit} → {converted_quantity} {new_unit}', 'success')
                        except Exception as e:
                            flash(f'Could not convert inventory to new unit: {str(e)}. Unit changed but quantity kept as-is.', 'warning')
                    else:
                        flash(f'Unit changed from {item.unit} to {new_unit}. Inventory quantity unchanged.', 'info')

                    # Clear the pending change
                    session.pop('pending_unit_change', None)

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
                from app.blueprints.fifo.services import update_fifo_perishable_status
                update_fifo_perishable_status(item.id, shelf_life_days)

    # Handle recount if quantity changed
    if new_quantity != item.quantity:
        from app.blueprints.fifo.services import recount_fifo
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
            unit=item.unit,  # Add the required unit field
            unit_cost=new_cost,
            note=f'Cost manually overridden from {item.cost_per_unit} to {new_cost}',
            created_by=current_user.id,
            quantity_used=0.0  # Cost overrides don't consume inventory - always null
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

    try:
        db.session.commit()
        flash(f'{item.type.title()} updated successfully.')
    except Exception as e:
        print(f"DEBUG: Error committing changes in edit_inventory: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f'Error saving changes: {str(e)}', 'error')

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


@inventory_bp.route('/debug/<int:id>')
@login_required
def debug_inventory(id):
    """Debug endpoint to check inventory status"""
    try:
        item = InventoryItem.query.get_or_404(id)

        # Check FIFO sync
        from app.services.inventory_adjustment import validate_inventory_fifo_sync
        is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(id)

        debug_info = {
            'item_id': item.id,
            'item_name': item.name,
            'item_quantity': item.quantity,
            'item_unit': item.unit,
            'item_type': item.type,
            'fifo_valid': is_valid,
            'fifo_error': error_msg,
            'inventory_qty': inv_qty,
            'fifo_total': fifo_total,
            'history_count': InventoryHistory.query.filter_by(inventory_item_id=id).count()
        }

        return jsonify(debug_info)

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500