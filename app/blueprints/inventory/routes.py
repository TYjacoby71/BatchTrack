from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory, Unit, IngredientCategory, User
from app.utils.permissions import permission_required
from app.utils.authorization import role_required
from app.utils.api_responses import api_error, api_success
from app.services.inventory_adjustment import process_inventory_adjustment, update_inventory_item
from app.services.inventory_alerts import InventoryAlertService
from app.services.reservation_service import ReservationService
from app.utils.timezone_utils import TimezoneUtils
import logging
from ...utils.unit_utils import get_global_unit_list
from ...utils.fifo_generator import get_change_type_prefix, int_to_base36
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

# Import the blueprint from __init__.py instead of creating a new one
from . import inventory_bp

@inventory_bp.route('/')
@login_required
def list_inventory():
    inventory_type = request.args.get('type')
    show_archived = request.args.get('show_archived') == 'true'
    query = InventoryItem.query

    # Add organization scoping - regular users only see their org's inventory
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)

    # Exclude product and product-reserved items from inventory management
    query = query.filter(~InventoryItem.type.in_(['product', 'product-reserved']))

    # Filter by archived status unless show_archived is true
    if not show_archived:
        query = query.filter(InventoryItem.is_archived != True)

    if inventory_type:
        query = query.filter_by(type=inventory_type)

    # Order by archived status (active items first) then by name
    query = query.order_by(InventoryItem.is_archived.asc(), InventoryItem.name.asc())
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

        # Calculate expired quantity using temporary attributes instead of properties
        if item.is_perishable:
            today = datetime.now().date()
            expired_entries = UnifiedInventoryHistory.query.filter(
                and_(
                    UnifiedInventoryHistory.inventory_item_id == item.id,
                    UnifiedInventoryHistory.remaining_quantity > 0,
                    UnifiedInventoryHistory.expiration_date != None,
                    UnifiedInventoryHistory.expiration_date < today
                )
            ).all()
            item.temp_expired_quantity = sum(float(entry.remaining_quantity) for entry in expired_entries)
            item.temp_available_quantity = float(item.quantity) - item.temp_expired_quantity
        else:
            item.temp_expired_quantity = 0
            item.temp_available_quantity = item.quantity

    return render_template('inventory_list.html',
                         inventory_items=inventory_items,
                         items=inventory_items,  # Template expects 'items'
                         categories=categories,
                         total_value=total_value,
                         units=units,
                         show_archived=show_archived,
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

    # Get scoped inventory item - regular users only see their org's inventory
    query = InventoryItem.query
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)
    item = query.filter_by(id=id).first_or_404()

    # Calculate freshness and expired quantities for this item (same as list_inventory)
    from ...blueprints.expiration.services import ExpirationService
    from datetime import datetime
    from sqlalchemy import and_

    item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)

    # Calculate expired quantity using temporary attributes
    if item.is_perishable:
        today = datetime.now().date()
        expired_entries_for_calc = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == item.id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today
            )
        ).all()
        item.temp_expired_quantity = sum(float(entry.remaining_quantity) for entry in expired_entries_for_calc)
        item.temp_available_quantity = float(item.quantity) - item.temp_expired_quantity
    else:
        item.temp_expired_quantity = 0
        item.temp_available_quantity = item.quantity

    history_query = UnifiedInventoryHistory.query.filter_by(inventory_item_id=id).options(
        joinedload(UnifiedInventoryHistory.batch),
        joinedload(UnifiedInventoryHistory.used_for_batch)
    )

    # Apply FIFO filter at database level if requested
    if fifo_filter:
        history_query = history_query.filter(UnifiedInventoryHistory.remaining_quantity > 0)

    history_query = history_query.order_by(UnifiedInventoryHistory.timestamp.desc())
    pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items

    from datetime import datetime

    # Get expired FIFO entries for display
    from sqlalchemy import and_
    expired_entries = []
    expired_total = 0
    if item.is_perishable:
        today = datetime.now().date()
        expired_entries = UnifiedInventoryHistory.query.filter(
            and_(
                UnifiedInventoryHistory.inventory_item_id == id,
                UnifiedInventoryHistory.remaining_quantity > 0,
                UnifiedInventoryHistory.expiration_date != None,
                UnifiedInventoryHistory.expiration_date < today
            )
        ).order_by(UnifiedInventoryHistory.expiration_date.asc()).all()
        expired_total = sum(float(entry.remaining_quantity) for entry in expired_entries)

    from ...utils.timezone_utils import TimezoneUtils
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
                         InventoryHistory=UnifiedInventoryHistory,
                         now=datetime.utcnow(),
                         get_change_type_prefix=get_change_type_prefix,
                         int_to_base36=int_to_base36,
                         fifo_filter=fifo_filter,
                         TimezoneUtils=TimezoneUtils)

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
        item_type = request.form.get('type', 'ingredient')  # 'ingredient', 'container', or 'product'
        # Handle cost entry type
        cost_entry_type = request.form.get('cost_entry_type', 'per_unit')
        cost_input = float(request.form.get('cost_per_unit', 0))

        if cost_entry_type == 'total' and quantity > 0:
            cost_per_unit = cost_input / quantity
        else:
            cost_per_unit = cost_input
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
        elif item_type == 'product':
            # Products use count by default but can have other units
            history_unit = unit if unit else 'count'
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

        # Set default notes if it's empty
        notes = request.form.get('notes', '')
        if not notes:
            notes = 'Initial stock creation'

        # Use centralized inventory adjustment service for proper FIFO tracking
        from app.services.inventory_adjustment import process_inventory_adjustment

        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=quantity,
            change_type='restock',
            unit=history_unit,
            notes=notes,
            created_by=current_user.id,
            cost_override=cost_per_unit,
            custom_expiration_date=item.expiration_date,
            custom_shelf_life_days=item.shelf_life_days
        )

        if not success:
            db.session.rollback()
            flash('Error creating inventory item - FIFO sync failed', 'error')
            return redirect(url_for('inventory.list_inventory'))

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
        return redirect(url_for('inventory.list_inventory'))
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
    item = InventoryItem.query.get_or_404(id)

    form = request.form
    adj_type = (form.get('adjustment_type') or form.get('change_type') or '').strip().lower()
    qty = float(form.get('quantity', 0) or 0.0)
    notes = form.get('notes') or None
    unit = form.get('input_unit') or getattr(item, 'unit', None)

    # Define all supported change types
    deductive_types = {
        'spoil', 'trash', 'expired', 'gift', 'sample', 'tester',
        'quality_fail', 'damaged', 'sold', 'sale', 'use', 'batch',
        'reserved', 'unreserved'
    }

    additive_types = {
        'restock', 'manual_addition', 'returned', 'refunded'
    }

    special_types = {
        'recount', 'cost_override'
    }

    try:
        # Recount (absolute target)
        if adj_type == 'recount':
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type='recount',
                unit=unit,
                notes=notes,
                created_by=getattr(current_user, 'id', None),
            )
            if success:
                flash('Inventory recount completed successfully.', 'success')
            else:
                flash('Error during recount adjustment.', 'error')
            return redirect(url_for('inventory.view_inventory', id=item.id))

        # Restock (with optional cost override for first-time)
        elif adj_type in additive_types:
            has_hist = InventoryHistory.query.filter_by(inventory_item_id=item.id).count() > 0
            cost_override = None

            if not has_hist and form.get('cost_entry_type') == 'per_unit' and form.get('cost_per_unit'):
                try:
                    cost_override = float(form.get('cost_per_unit'))
                except ValueError:
                    cost_override = None

            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type=adj_type,
                unit=unit,
                notes=notes,
                created_by=getattr(current_user, 'id', None),
                cost_override=cost_override,
            )
            if success:
                flash(f'Inventory {adj_type} completed successfully.', 'success')
            else:
                flash(f'Error during {adj_type} adjustment.', 'error')
            return redirect(url_for('inventory.view_inventory', id=item.id))

        # Deductive adjustments (spoil, trash, etc.)
        elif adj_type in deductive_types:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,  # Service will make this negative
                change_type=adj_type,
                unit=unit,
                notes=notes,
                created_by=getattr(current_user, 'id', None),
            )
            if success:
                flash(f'Inventory {adj_type} completed successfully.', 'success')
            else:
                flash(f'Error during {adj_type} adjustment.', 'error')
            return redirect(url_for('inventory.view_inventory', id=item.id))

        # Cost override
        elif adj_type == 'cost_override':
            new_cost = float(form.get('cost_per_unit', 0))
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=0,  # No quantity change for cost override
                change_type='cost_override',
                unit=unit,
                notes=notes or f'Cost override to {new_cost}',
                created_by=getattr(current_user, 'id', None),
                cost_override=new_cost,
            )
            if success:
                flash('Cost override completed successfully.', 'success')
            else:
                flash('Error during cost override.', 'error')
            return redirect(url_for('inventory.view_inventory', id=item.id))

        else:
            flash(f'Invalid adjustment type: {adj_type}', 'error')
            return redirect(url_for('inventory.view_inventory', id=item.id))

    except Exception as e:
        flash(f'Error processing adjustment: {str(e)}', 'error')
        return redirect(url_for('inventory.view_inventory', id=item.id))


@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_inventory(id):
    # Get scoped inventory item first to ensure access
    query = InventoryItem.query
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)
    item = query.filter_by(id=id).first_or_404()
    
    success, message = update_inventory_item(id, request.form.to_dict())
    flash(message, 'success' if success else 'error')
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
            'history_count': UnifiedInventoryHistory.query.filter_by(inventory_item_id=id).count()
        }

        return jsonify(debug_info)

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500