# app/blueprints/inventory/routes.py

import logging
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

from app.models import (IngredientCategory, InventoryHistory, InventoryItem,
                        User, db)
from app.utils.api_responses import api_error
from app.utils.unit_utils import get_global_unit_list
# This is the ONLY service needed for adjustments now.
from app.services.inventory_adjustment import process_inventory_adjustment, validate_inventory_fifo_sync
# We will need the expiration service for display logic until we refactor it.
from app.blueprints.expiration.services import ExpirationService

# Import the blueprint from __init__.py instead of creating a new one
from . import inventory_bp

logger = logging.getLogger(__name__)


@inventory_bp.route('/')
@login_required
def list_inventory():
    """Renders the main inventory list page, including freshness and expiration data."""
    inventory_type = request.args.get('type')
    show_archived = request.args.get('show_archived') == 'true'
    query = InventoryItem.query.filter_by(organization_id=current_user.organization_id)

    query = query.filter(~InventoryItem.type.in_(['product', 'product-reserved']))

    if not show_archived:
        query = query.filter(InventoryItem.is_archived != True)

    if inventory_type:
        query = query.filter_by(type=inventory_type)

    inventory_items = query.order_by(InventoryItem.is_archived.asc(), InventoryItem.name.asc()).all()
    categories = IngredientCategory.query.all()
    total_value = sum(item.quantity * item.cost_per_unit for item in inventory_items if item.quantity and item.cost_per_unit)
    units = get_global_unit_list()

    # --- THIS IS THE LOGIC THAT WAS MISSING ---
    for item in inventory_items:
        item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)

        # Calculate expired and available quantities for display
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
            item.temp_expired_quantity = sum(float(entry.remaining_quantity) for entry in expired_entries)
            item.temp_available_quantity = float(item.quantity) - item.temp_expired_quantity
        else:
            item.temp_expired_quantity = 0
            item.temp_available_quantity = item.quantity
    # --- END OF MISSING LOGIC ---

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
    """Saves user's column visibility preferences to the session."""
    columns = request.form.getlist('columns')
    session['inventory_columns'] = columns
    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/view/<int:id>')
@login_required
def view_inventory(id):
    """Renders the detailed view for a single inventory item."""
    page = request.args.get('page', 1, type=int)
    per_page = 5
    fifo_filter = request.args.get('fifo') == 'true'

    # Get scoped inventory item - regular users only see their org's inventory
    item = InventoryItem.query.filter_by(id=id, organization_id=current_user.organization_id).first_or_404()

    history_query = InventoryHistory.query.filter_by(inventory_item_id=id).options(
        joinedload(InventoryHistory.batch),
        joinedload(InventoryHistory.used_for_batch)
    )

    # Apply FIFO filter at database level if requested
    if fifo_filter:
        history_query = history_query.filter(InventoryHistory.remaining_quantity > 0)

    history_query = history_query.order_by(InventoryHistory.timestamp.desc())
    pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items

    # --- THIS IS THE LOGIC THAT WAS MISSING ---
    item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)
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
        item.temp_expired_quantity = sum(float(entry.remaining_quantity) for entry in expired_entries)
        item.temp_available_quantity = float(item.quantity) - item.temp_expired_quantity
    else:
        item.temp_expired_quantity = 0
        item.temp_available_quantity = item.quantity
    # --- END OF MISSING LOGIC ---

    # Get expired FIFO entries for display
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
        expired_total = sum(float(entry.remaining_quantity) for entry in expired_entries)

    from app.utils.timezone_utils import TimezoneUtils
    from app.utils.fifo_generator import get_change_type_prefix, int_to_base36
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
                           fifo_filter=fifo_filter,
                           TimezoneUtils=TimezoneUtils)


@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    """Handles the creation of a new inventory item."""
    name = request.form.get('name')
    if not name:
        flash('Item name is required.', 'error')
        return redirect(url_for('inventory.list_inventory'))

    existing_item = InventoryItem.query.filter_by(name=name, organization_id=current_user.organization_id).first()
    if existing_item:
        flash(f'An item named "{name}" already exists.', 'error')
        return redirect(url_for('inventory.list_inventory'))

    try:
        quantity = float(request.form.get('quantity', 0))
        unit = request.form.get('unit')
        item_type = request.form.get('type', 'ingredient')
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
                from datetime import timedelta
                expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)

        # Handle container-specific fields and unit assignment
        storage_amount = None
        storage_unit = None
        if item_type == 'container':
            storage_amount = float(request.form.get('storage_amount', 0))
            storage_unit = request.form.get('storage_unit')
            unit = ''  # Containers don't have a unit on the item itself
            history_unit = 'count'  # But history entries use 'count'
        elif item_type == 'product':
            history_unit = unit if unit else 'count'
        else:
            history_unit = unit

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
        db.session.flush()

        notes = request.form.get('notes', '')
        if not notes:
            notes = 'Initial stock creation'

        if quantity > 0:
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
        flash('Inventory item added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding inventory item: {e}", exc_info=True)
        flash(f'Error adding item: {str(e)}', 'error')

    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
@login_required
def adjust_inventory(id):
    """A single, clean route to handle ALL inventory adjustments."""
    item = InventoryItem.query.get_or_404(id)
    if item.organization_id != current_user.organization_id:
        flash("You do not have permission to adjust this item.", "error")
        return redirect(url_for('inventory.list_inventory'))

    try:
        form = request.form
        adj_type = (form.get('adjustment_type') or form.get('change_type') or '').strip().lower()
        quantity_str = form.get('quantity', '0.0')
        notes = form.get('notes')
        unit = form.get('input_unit') or item.unit

        if not adj_type:
            raise ValueError("An adjustment type (e.g., 'spoil', 'recount') is required.")

        quantity = float(quantity_str)

        # Handle cost override for restock operations
        cost_override = None
        if adj_type == 'restock':
            has_hist = InventoryHistory.query.filter_by(inventory_item_id=item.id).count() > 0
            if not has_hist and form.get('cost_entry_type') == 'per_unit' and form.get('cost_per_unit'):
                try:
                    cost_override = float(form.get('cost_per_unit'))
                except ValueError:
                    cost_override = None

        success = process_inventory_adjustment(
            item_id=id,
            quantity=quantity,
            change_type=adj_type,
            unit=unit,
            notes=notes,
            created_by=current_user.id,
            cost_override=cost_override
        )

        if success:
            flash(f'Inventory adjustment "{adj_type.replace("_", " ").title()}" was successful.', 'success')
        else:
            flash(f'Inventory adjustment "{adj_type}" failed.', 'error')

    except ValueError as e:
        flash(f'Adjustment failed: {str(e)}', 'error')
    except Exception as e:
        flash(f'An unexpected server error occurred. Please contact support.', 'error')
        logger.error(f"Unexpected error in adjust_inventory for item {id}: {e}", exc_info=True)

    return redirect(url_for('inventory.view_inventory', id=id))


@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_inventory(id):
    """Handles updates to an inventory item's details."""
    item = InventoryItem.query.get_or_404(id)
    if item.organization_id != current_user.organization_id:
        flash("You do not have permission to edit this item.", "error")
        return redirect(url_for('inventory.list_inventory'))

    try:
        item.name = request.form.get('name', item.name)
        item.low_stock_threshold = float(request.form.get('low_stock_threshold', item.low_stock_threshold or 0.0))

        # Handle quantity changes via recount
        new_quantity_str = request.form.get('quantity', '')
        if new_quantity_str and new_quantity_str.strip():
            new_quantity = float(new_quantity_str)
            if new_quantity != item.quantity:
                notes = "Manual quantity update via inventory edit"
                success = process_inventory_adjustment(
                    item_id=item.id,
                    quantity=new_quantity,
                    change_type='recount',
                    unit=item.unit,
                    notes=notes,
                    created_by=current_user.id
                )
                if not success:
                    flash('Error updating quantity', 'error')
                    return redirect(url_for('inventory.view_inventory', id=id))

        db.session.commit()
        flash(f'"{item.name}" updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing inventory item {id}: {e}", exc_info=True)
        flash(f'Error updating item: {str(e)}', 'error')

    return redirect(url_for('inventory.view_inventory', id=id))


@inventory_bp.route('/archive/<int:id>')
@login_required
def archive_inventory(id):
    """Archives an inventory item."""
    item = InventoryItem.query.get_or_404(id)
    if item.organization_id != current_user.organization_id:
        flash("You do not have permission to archive this item.", "error")
        return redirect(url_for('inventory.list_inventory'))

    try:
        item.is_archived = True
        db.session.commit()
        flash(f'"{item.name}" has been archived.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error archiving item {id}: {e}", exc_info=True)
        flash(f'Error archiving item: {str(e)}', 'error')

    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/restore/<int:id>')
@login_required
def restore_inventory(id):
    """Restores an archived inventory item."""
    item = InventoryItem.query.get_or_404(id)
    if item.organization_id != current_user.organization_id:
        flash("You do not have permission to restore this item.", "error")
        return redirect(url_for('inventory.list_inventory'))

    try:
        item.is_archived = False
        db.session.commit()
        flash(f'"{item.name}" has been restored.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error restoring item {id}: {e}", exc_info=True)
        flash(f'Error restoring item: {str(e)}', 'error')

    return redirect(url_for('inventory.list_inventory', show_archived='true'))


@inventory_bp.route('/debug/<int:id>')
@login_required
def debug_inventory(id):
    """Provides a JSON endpoint to check the sync status of an inventory item."""
    item = InventoryItem.query.get_or_404(id)
    if item.organization_id != current_user.organization_id:
        return jsonify(api_error("Permission denied")), 403

    try:
        is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(id)

        debug_info = {
            'item_id': item.id,
            'item_name': item.name,
            'item_quantity': item.quantity,
            'item_unit': item.unit,
            'item_type': item.type,
            'fifo_is_synced': is_valid,
            'fifo_sync_message': error_msg,
            'inventory_quantity_db': inv_qty,
            'fifo_total_calculated': fifo_total,
            'history_entry_count': InventoryHistory.query.filter_by(inventory_item_id=id).count()
        }
        return jsonify(debug_info)

    except Exception as e:
        import traceback
        logger.error(f"Error in debug_inventory for item {id}: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500