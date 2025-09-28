from flask import Blueprint, request, jsonify, render_template, redirect, flash, session, url_for
from flask_login import login_required, current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory, Unit, IngredientCategory, User
from app.utils.permissions import permission_required, role_required
from app.utils.api_responses import api_error, api_success
from app.services.inventory_adjustment import process_inventory_adjustment, update_inventory_item, create_inventory_item
from app.services.inventory_alerts import InventoryAlertService
from app.services.reservation_service import ReservationService
from app.utils.timezone_utils import TimezoneUtils
import logging
from ...utils.unit_utils import get_global_unit_list
# Removed deprecated get_change_type_prefix import - functionality moved to generate_fifo_code
from ...utils.fifo_generator import int_to_base36
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload
from app.models.inventory_lot import InventoryLot
from app.services.density_assignment_service import DensityAssignmentService # Added for density assignment

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

@inventory_bp.route('/api/get-item/<int:item_id>')
@login_required
def api_get_inventory_item(item_id):
    """Return inventory item details for the edit modal (org-scoped)."""
    try:
        query = InventoryItem.query
        if current_user.organization_id:
            query = query.filter_by(organization_id=current_user.organization_id)
        item = query.filter_by(id=item_id).first()
        if not item:
            return jsonify({'error': 'Item not found'}), 404

        return jsonify({
            'id': item.id,
            'name': item.name,
            'quantity': float(item.quantity or 0),
            'unit': item.unit,
            'cost_per_unit': float(item.cost_per_unit or 0),
            'type': item.type,
            'global_item_id': getattr(item, 'global_item_id', None),
            'category_id': getattr(item, 'category_id', None),
            'density': item.density,
            'is_perishable': bool(item.is_perishable),
            'shelf_life_days': item.shelf_life_days,
            'capacity': getattr(item, 'capacity', None),
            'capacity_unit': getattr(item, 'capacity_unit', None),
            'container_material': getattr(item, 'container_material', None),
            'container_type': getattr(item, 'container_type', None),
            'container_style': getattr(item, 'container_style', None),
            'notes': ''
        })
    except Exception as e:
        logger.exception('Failed to load inventory item for edit modal')
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/api/quick-create', methods=['POST'])
@login_required
def api_quick_create_inventory():
    """JSON endpoint to quickly create an inventory item (zero qty) and return it.
    Uses existing create_inventory_item service. Org-scoped.
    Expected JSON:
      { name, type, unit?, global_item_id?, category_id?/ref_*, density?, capacity?, capacity_unit? }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}

        # Normalize form-like dict for service
        form_like = {}
        for key, value in (data.items() if hasattr(data, 'items') else []):
            form_like[str(key)] = value if value is not None else ''

        success, message, item_id = create_inventory_item(
            form_data=form_like,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )

        if not success or not item_id:
            return jsonify({
                'success': False,
                'error': message or 'Failed to create inventory item'
            }), 400

        item = db.session.get(InventoryItem, int(item_id))
        if not item:
            return jsonify({'success': False, 'error': 'Created item not found'}), 500

        return jsonify({
            'success': True,
            'item': {
                'id': item.id,
                'name': item.name,
                'unit': item.unit,
                'type': item.type,
                'global_item_id': getattr(item, 'global_item_id', None),
            }
        })

    except Exception as e:
        logging.exception('Quick-create inventory failed')
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/')
@login_required
def list_inventory():
    inventory_type = request.args.get('type')
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category')
    show_archived = request.args.get('show_archived') == 'true'
    show_zero_qty = request.args.get('show_zero_qty', 'true') == 'true'  # Show zero quantity by default
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

    if not show_zero_qty:
        query = query.filter(InventoryItem.quantity > 0)

    ingredients = query.all()
    units = get_global_unit_list()
    categories = IngredientCategory.query.all()
    total_value = sum(item.quantity * item.cost_per_unit for item in ingredients)

    # Calculate freshness and expired quantities for each item
    from ...blueprints.expiration.services import ExpirationService
    from datetime import datetime
    from sqlalchemy import and_

    for item in ingredients:
        item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)

        # Calculate expired quantity using only InventoryLot (lots handle FIFO tracking now)
        if item.is_perishable:
            today = datetime.now().date()
            # Only check InventoryLot for expired quantities
            expired_lots = InventoryLot.query.filter(
                and_(
                    InventoryLot.inventory_item_id == item.id,
                    InventoryLot.remaining_quantity > 0,
                    InventoryLot.expiration_date != None,
                    InventoryLot.expiration_date < today
                )
            ).all()

            item.temp_expired_quantity = sum(float(lot.remaining_quantity) for lot in expired_lots)
            item.temp_available_quantity = float(item.quantity) - item.temp_expired_quantity
        else:
            item.temp_expired_quantity = 0
            item.temp_available_quantity = item.quantity

    return render_template('inventory_list.html',
                         inventory_items=ingredients,
                         items=ingredients,  # Template expects 'items'
                         categories=categories,
                         total_value=total_value,
                         units=units,
                         show_archived=show_archived,
                         show_zero_qty=show_zero_qty,
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
    item = query.filter_by(id=id).first()

    if not item:
        flash('Inventory item not found or access denied.', 'error')
        return redirect(url_for('inventory.list_inventory'))

    # Calculate freshness and expired quantities for this item (same as list_inventory)
    from ...blueprints.expiration.services import ExpirationService
    from datetime import datetime
    from sqlalchemy import and_

    item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)

    # Calculate expired quantity using only InventoryLot (lots handle FIFO tracking now)
    if item.is_perishable:
        today = datetime.now().date()
        # Only check InventoryLot for expired quantities
        expired_lots_for_calc = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item.id,
                InventoryLot.remaining_quantity > 0,
                InventoryLot.expiration_date != None,
                InventoryLot.expiration_date < today
            )
        ).all()

        item.temp_expired_quantity = sum(float(lot.remaining_quantity) for lot in expired_lots_for_calc)
        item.temp_available_quantity = float(item.quantity) - item.temp_expired_quantity
    else:
        item.temp_expired_quantity = 0
        item.temp_available_quantity = float(item.quantity)

    # Ensure these attributes are always set for template display
    if not hasattr(item, 'temp_expired_quantity'):
        item.temp_expired_quantity = 0
    if not hasattr(item, 'temp_available_quantity'):
        item.temp_available_quantity = float(item.quantity)

    history_query = UnifiedInventoryHistory.query.filter_by(inventory_item_id=id).options(
        joinedload(UnifiedInventoryHistory.batch),
        joinedload(UnifiedInventoryHistory.used_for_batch),
        joinedload(UnifiedInventoryHistory.affected_lot)
    )

    # Lots: retrieve via FIFO service to preserve service authority
    history_query = history_query.order_by(UnifiedInventoryHistory.timestamp.desc())

    pagination = history_query.paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items
    # When FIFO toggle is ON, show ALL lots (including depleted ones)
    # When FIFO toggle is OFF, show only active lots
    lots_query = InventoryLot.query.filter_by(inventory_item_id=id)
    if not fifo_filter:  # fifo_filter=False means show only active lots
        lots_query = lots_query.filter(InventoryLot.remaining_quantity > 0)
    lots = lots_query.order_by(InventoryLot.created_at.asc()).all()

    from datetime import datetime

    # Get expired FIFO entries for display (only from InventoryLot since lots handle FIFO tracking)
    from sqlalchemy import and_

    expired_entries = []
    expired_total = 0
    if item.is_perishable:
        today = datetime.now().date()
        # Only check InventoryLot for expired entries
        expired_entries = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == id,
                InventoryLot.remaining_quantity > 0,
                InventoryLot.expiration_date != None,
                InventoryLot.expiration_date < today
            )
        ).order_by(InventoryLot.expiration_date.asc()).all()

        expired_total = sum(float(lot.remaining_quantity) for lot in expired_entries)

    from ...utils.timezone_utils import TimezoneUtils
    return render_template('pages/inventory/view.html',
                         abs=abs,
                         item=item,
                         history=history,
                         lots=lots,
                         pagination=pagination,
                         expired_entries=expired_entries,
                         expired_total=expired_total,
                         units=get_global_unit_list(),
                         get_global_unit_list=get_global_unit_list,
                         get_ingredient_categories=IngredientCategory.query.order_by(IngredientCategory.name).all,
                         User=User,
                         UnifiedInventoryHistory=UnifiedInventoryHistory,
                         now=datetime.utcnow(),
                         int_to_base36=int_to_base36,
                         fifo_filter=fifo_filter,
                         TimezoneUtils=TimezoneUtils)

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    """Create new inventory items"""
    try:
        logger.info(f"CREATE NEW INVENTORY ITEM - User: {current_user.id}, Org: {current_user.organization_id}")

        success, message, item_id = create_inventory_item(
            form_data=request.form.to_dict(),
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )

        if success:
            # Ensure database transaction is committed
            db.session.commit()
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
    """Handle inventory adjustments"""
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

        # Extract optional parameters
        cost_override = None
        # Support either per-unit or total cost entry; if total, convert to per-unit
        raw_cost = form_data.get('cost_per_unit')
        cost_entry_type = (form_data.get('cost_entry_type') or 'no_change').strip().lower()
        if raw_cost not in (None, ''):
            try:
                parsed_cost = float(raw_cost)
                if cost_entry_type == 'total':
                    qty_val = float(form_data.get('quantity', 0.0) or 0.0)
                    if qty_val <= 0:
                        flash("Total cost requires a positive quantity.", "error")
                        return redirect(url_for('.view_inventory', id=item_id))
                    cost_override = parsed_cost / qty_val
                else:
                    cost_override = parsed_cost
            except (ValueError, TypeError):
                flash("Invalid cost provided.", "error")
                return redirect(url_for('.view_inventory', id=item_id))

        custom_expiration_date = form_data.get('custom_expiration_date')
        custom_shelf_life_days = form_data.get('custom_shelf_life_days')
        notes = form_data.get('notes', '')
        input_unit = form_data.get('input_unit') or item.unit or 'count'

        # Call the central inventory adjustment service
        success, message = process_inventory_adjustment(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            notes=notes,
            created_by=current_user.id,
            cost_override=cost_override,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            unit=input_unit
        )

        # Flash result and redirect
        if success:
            flash(f'{change_type.title()} completed: {message}', 'success')
            logger.info(f"Adjustment successful: {message}")
        else:
            flash(f'Adjustment failed: {message}', 'error')
            logger.error(f"Adjustment failed: {message}")

        return redirect(url_for('.view_inventory', id=item_id))

    except Exception as e:
        logger.error(f"Error in adjust_inventory route: {str(e)}")
        flash(f'System error during adjustment: {str(e)}', 'error')
        return redirect(url_for('.view_inventory', id=item_id))

@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_inventory(id):
    """Handle inventory item editing and recounts"""
    try:
        # Get scoped inventory item first to ensure access
        query = InventoryItem.query
        if current_user.organization_id:
            query = query.filter_by(organization_id=current_user.organization_id)
        item = query.filter_by(id=id).first_or_404()

        # Authority check
        if not can_edit_inventory_item(item):
            flash('Permission denied.', 'error')
            return redirect(url_for('inventory.view_inventory', id=id))

        # Extract form data
        form_data = request.form.to_dict()
        logger.info(f"EDIT INVENTORY - Item: {item.name} (ID: {id})")

        # Enforce global item type validation if linked
        try:
            from app.models import GlobalItem
            new_type = form_data.get('type', item.type)
            if getattr(item, 'global_item_id', None):
                gi = db.session.get(GlobalItem, int(item.global_item_id))
                if gi and gi.item_type != new_type:
                    flash(f"Type '{new_type}' does not match linked global item type '{gi.item_type}'.", 'error')
                    return redirect(url_for('inventory.view_inventory', id=id))
        except Exception as _e:
            # Fail closed with informative error if validation cannot complete
            logger.warning(f"Global item type validation skipped due to error: {_e}")

        # Check if this is a quantity recount
        new_quantity = form_data.get('quantity')
        recount_performed = False

        if new_quantity is not None and new_quantity != '':
            try:
                target_quantity = float(new_quantity)
                logger.info(f"QUANTITY RECOUNT: Target quantity {target_quantity} for item {item.name}")

                # Use central inventory adjustment service for recount
                success, message = process_inventory_adjustment(
                    item_id=item.id,
                    quantity=target_quantity,
                    change_type='recount',
                    notes=f'Inventory recount via edit form - target: {target_quantity}',
                    created_by=current_user.id,
                    target_quantity=target_quantity
                )

                if not success:
                    flash(f'Recount failed: {message}', 'error')
                    return redirect(url_for('inventory.view_inventory', id=id))

                logger.info(f"RECOUNT SUCCESS: {message}")
                recount_performed = True

            except (ValueError, TypeError):
                flash("Invalid quantity provided for recount.", "error")
                return redirect(url_for('inventory.view_inventory', id=id))

        # Handle other field updates
        update_form_data = form_data.copy()
        if recount_performed:
            update_form_data.pop('quantity', None)

        # Enforce immutability for globally-managed identity fields
        is_global_locked = getattr(item, 'global_item_id', None) is not None

        # Update basic fields
        if not is_global_locked:
            item.name = form_data.get('name', item.name)
        else:
            # Ignore attempted name changes
            form_data['name'] = item.name

        # Unit can be changed only if not global locked
        if not is_global_locked:
            item.unit = form_data.get('unit', item.unit)
        item.cost_per_unit = float(form_data.get('cost_per_unit', item.cost_per_unit or 0))
        item.low_stock_threshold = float(form_data.get('low_stock_threshold', item.low_stock_threshold or 0))
        item.type = form_data.get('type', item.type)

        # Handle category (only for ingredients)
        if item.type == 'ingredient':
            raw_category_id = form_data.get('category_id')
            if raw_category_id and not is_global_locked:
                try:
                    parsed_category_id = int(raw_category_id)
                    item.category_id = parsed_category_id
                    # Apply category default density when category is chosen
                    try:
                        cat_obj = db.session.get(IngredientCategory, parsed_category_id)
                        if cat_obj and cat_obj.default_density and cat_obj.default_density > 0:
                            item.density = cat_obj.default_density
                            item.density_source = 'category_default'
                        else:
                            item.density_source = 'manual'
                    except Exception:
                        item.density_source = 'manual'
                except (ValueError, TypeError):
                    logger.warning(f"Invalid category_id provided: {raw_category_id}")
            else:
                item.category_id = None
                item.density_source = 'manual'
        else:
            item.category_id = None

        # Handle container-specific fields
        if item.type == 'container':
            capacity = form_data.get('capacity')
            capacity_unit = form_data.get('capacity_unit')
            logger.info(f"Container update - capacity: {capacity}, capacity_unit: {capacity_unit}")
            if capacity:
                old_capacity = item.capacity
                item.capacity = float(capacity)
                logger.info(f"Updated capacity: {old_capacity} -> {item.capacity}")
            if capacity_unit:
                old_capacity_unit = item.capacity_unit
                item.capacity_unit = capacity_unit
                logger.info(f"Updated capacity_unit: {old_capacity_unit} -> {item.capacity_unit}")

            # Containers are always counted by "count" - never use capacity_unit as the item unit
            item.unit = 'count'
            logger.info(f"Container unit set to 'count' (capacity unit is {item.capacity_unit})")

        # Prevent density changes if globally locked
        if is_global_locked:
            update_form_data.pop('density', None)
            update_form_data.pop('item_density', None)
            update_form_data.pop('category_id', None)
            update_form_data.pop('unit', None)
        success, message = update_inventory_item(id, update_form_data)
        flash(message, 'success' if success else 'error')
        return redirect(url_for('inventory.view_inventory', id=id))

    except Exception as e:
        logger.error(f"Error in edit_inventory route: {str(e)}")
        flash(f'System error during edit: {str(e)}', 'error')
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