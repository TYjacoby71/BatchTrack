from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory, Unit, IngredientCategory, User
from app.utils.permissions import permission_required
from app.utils.permissions import role_required
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

logger = logging.getLogger(__name__)

def can_edit_inventory_item(item):
    """Helper function to check if current user can edit an inventory item"""
    if not current_user.is_authenticated:
        return False
    if current_user.user_type == 'developer':
        return True
    return item.organization_id == current_user.organization_id

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
        expired_entries_for_calc = UnifiedInventoryHistory.query.filter(
            and_(
                UnifiedInventoryHistory.inventory_item_id == item.id,
                UnifiedInventoryHistory.remaining_quantity > 0,
                UnifiedInventoryHistory.expiration_date != None,
                UnifiedInventoryHistory.expiration_date < today
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
    return render_template('pages/inventory/view.html',
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
                         UnifiedInventoryHistory=UnifiedInventoryHistory,
                         now=datetime.utcnow(),
                         get_change_type_prefix=get_change_type_prefix,
                         int_to_base36=int_to_base36,
                         fifo_filter=fifo_filter,
                         TimezoneUtils=TimezoneUtils)

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    """
    INVENTORY CREATION Route - creates entirely new inventory items.
    This is for adding new ingredients/containers (mangoes, oranges), NOT adjusting existing ones.
    """
    try:
        logger.info(f"CREATE NEW INVENTORY ITEM - User: {current_user.id}, Org: {current_user.organization_id}")
        logger.info(f"Form data: {dict(request.form)}")

        from app.services.inventory_adjustment import create_inventory_item

        success, message, item_id = create_inventory_item(
            form_data=request.form.to_dict(),
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )

        if success:
            flash(f'New inventory item created: {message}', 'success')
            if item_id:
                return redirect(url_for('inventory.view_inventory', id=item_id))
        else:
            flash(f'Failed to create inventory item: {message}', 'error')

        return redirect(url_for('inventory.list_inventory'))

    except Exception as e:
        logger.error(f"Error in add_inventory route: {str(e)}")
        flash(f'System error creating inventory: {str(e)}', 'error')
        return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust/<int:item_id>', methods=['POST'])
@login_required
def adjust_inventory(item_id):
    """
    INVENTORY ADJUSTMENT Route - handles updates to existing inventory.
    This is for adding/removing/spoiling existing items, NOT creating new items.
    """
    try:
        item = db.session.get(InventoryItem, int(item_id))
        if not item:
            flash("Inventory item not found.", "error")
            return redirect(url_for('.list_inventory'))

        # Authority check
        if not can_edit_inventory_item(item):
            flash('Permission denied.', 'error')
            return redirect(url_for('.list_inventory'))

        # Extract and validate form data
        form_data = request.form
        logger.info(f"ADJUST INVENTORY - Item: {item.name} (ID: {item_id})")
        logger.info(f"Form data received: {dict(form_data)}")

        # Validate required fields
        change_type = form_data.get('change_type', '').strip().lower()
        if not change_type:
            flash("Adjustment type is required.", "error")
            return redirect(url_for('.view_inventory', id=item_id))

        try:
            quantity = float(form_data.get('quantity', 0.0))
            if quantity <= 0:
                flash("Quantity must be greater than 0.", "error")
                return redirect(url_for('.view_inventory', id=item_id))
        except (ValueError, TypeError):
            flash("Invalid quantity provided.", "error")
            return redirect(url_for('.view_inventory', id=item_id))

        # Extract optional cost override
        cost_override = None
        if form_data.get('cost_per_unit'):
            try:
                cost_override = float(form_data.get('cost_per_unit'))
            except (ValueError, TypeError):
                flash("Invalid cost per unit provided.", "error")
                return redirect(url_for('.view_inventory', id=item_id))

        # Call the canonical inventory adjustment service
        success, message = process_inventory_adjustment(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            notes=form_data.get('notes', ''),
            unit=form_data.get('input_unit') or item.unit or 'count',
            cost_override=cost_override,
            created_by=current_user.id
        )

        # Flash result and redirect
        if success:
            flash(f'{change_type.title()} completed: {message}', 'success')
        else:
            flash(f'Adjustment failed: {message}', 'error')

        return redirect(url_for('.view_inventory', id=item_id))

    except Exception as e:
        logger.error(f"Error in adjust_inventory route: {str(e)}")
        flash(f'System error during adjustment: {str(e)}', 'error')
        return redirect(url_for('.view_inventory', id=item_id))


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