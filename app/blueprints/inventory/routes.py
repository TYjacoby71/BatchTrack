from datetime import datetime, timezone

from types import SimpleNamespace

from flask import Blueprint, url_for, request, jsonify, render_template, redirect, flash, session, current_app
from flask_login import login_required, current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory, Unit, IngredientCategory, User, GlobalItem
from app.utils.permissions import permission_required, role_required
from app.utils.api_responses import api_error, api_success
from app.extensions import cache, limiter
from app.services.inventory_adjustment import process_inventory_adjustment, update_inventory_item, create_inventory_item
from app.services.inventory_alerts import InventoryAlertService
from app.services.reservation_service import ReservationService
from app.utils.timezone_utils import TimezoneUtils
import logging
from ...utils.unit_utils import get_global_unit_list
from ...utils.inventory_event_code_generator import int_to_base36
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload, selectinload
from app.models.inventory_lot import InventoryLot
from app.services.density_assignment_service import DensityAssignmentService # Added for density assignment
from app.services.bulk_inventory_service import BulkInventoryService, BulkInventoryServiceError
from datetime import datetime, timezone # Fix missing timezone import

# Import the blueprint from __init__.py instead of creating a new one
from . import inventory_bp
from app.services.cache_invalidation import inventory_list_cache_key
from app.utils.cache_utils import should_bypass_cache

logger = logging.getLogger(__name__)


def _expired_quantity_map(item_ids):
    if not item_ids:
        return {}
    today = TimezoneUtils.utc_now().date()
    rows = (
        db.session.query(
            InventoryLot.inventory_item_id,
            func.sum(InventoryLot.remaining_quantity),
        )
        .filter(
            InventoryLot.inventory_item_id.in_(item_ids),
            InventoryLot.remaining_quantity > 0,
            InventoryLot.expiration_date != None,
            InventoryLot.expiration_date < today,
        )
        .group_by(InventoryLot.inventory_item_id)
        .all()
    )
    return {row[0]: float(row[1] or 0) for row in rows}


def _extract_queue_code_from_notes(notes: str | None) -> str | None:
    if not notes:
        return None
    tag_start = notes.find('[QUEUE:')
    if tag_start == -1:
        return None
    tag_end = notes.find(']', tag_start)
    if tag_end == -1:
        return None
    tag = notes[tag_start + 7:tag_end]
    parts = [p.strip() for p in tag.split('|') if p.strip()]
    for part in parts:
        if part.startswith('CODE:'):
            return part.split('CODE:', 1)[1]
    return None


def _serialize_inventory_items(items):
    from ...blueprints.expiration.services import ExpirationService

    serialized = []
    total_value = 0.0
    perishable_ids = [item.id for item in items if item.is_perishable]
    expired_map = _expired_quantity_map(perishable_ids)

    for item in items:
        quantity = float(item.quantity or 0.0)
        total_value += quantity * float(item.cost_per_unit or 0.0)
        expired_qty = expired_map.get(item.id, 0.0)
        available_qty = max(0.0, quantity - expired_qty)
        freshness = (
            ExpirationService.get_weighted_average_freshness(item.id)
            if item.is_perishable
            else None
        )

        serialized.append(
            {
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "unit": item.unit,
                "quantity": quantity,
                "temp_available_quantity": available_qty,
                "temp_expired_quantity": expired_qty,
                "density": float(item.density) if item.density is not None else None,
                "cost_per_unit": float(item.cost_per_unit or 0.0),
                "freshness_percent": freshness,
                "is_perishable": bool(item.is_perishable),
                "is_archived": bool(item.is_archived),
                "low_stock_threshold": float(item.low_stock_threshold or 0.0),
                "global_item_id": item.global_item_id,
                "global_item_name": getattr(item.global_item, "name", None),
                "global_item_category": getattr(
                    getattr(item.global_item, "ingredient_category", None), "name", None
                ),
                "category_name": getattr(getattr(item, "category", None), "name", None),
                "capacity": item.capacity,
                "capacity_unit": item.capacity_unit,
                "container_material": item.container_material,
                "container_type": item.container_type,
                "container_style": item.container_style,
                "container_color": item.container_color,
            }
        )
    return serialized, total_value


def _hydrate_inventory_items(serialized_items):
    hydrated = []
    for entry in serialized_items:
        data = dict(entry)
        category_name = data.pop("category_name", None)
        global_item_name = data.pop("global_item_name", None)
        global_item_category = data.pop("global_item_category", None)
        global_item_id = data.get("global_item_id")

        item = SimpleNamespace(**data)
        item.category = SimpleNamespace(name=category_name) if category_name else None

        if global_item_id:
            ingredient_category = (
                SimpleNamespace(name=global_item_category)
                if global_item_category
                else None
            )
            item.global_item = SimpleNamespace(
                id=global_item_id,
                name=global_item_name,
                ingredient_category=ingredient_category,
            )
        else:
            item.global_item = None

        hydrated.append(item)
    return hydrated

def can_edit_inventory_item(item):
    """Helper function to check if current user can edit an inventory item"""
    if not current_user.is_authenticated:
        return False
    if current_user.user_type == 'developer':
        return True
    return item.organization_id == current_user.organization_id

@inventory_bp.route('/api/search')
@login_required
@limiter.limit("2000/minute")
def api_search_inventory():
    """Search inventory items by name (org-scoped), optionally filtered by type.

    Query params:
      - q: search text (min 2 chars)
      - type: optional inventory type (e.g., 'container', 'ingredient')
      - change_type: optional change context ('create', 'restock', etc.)

    Returns JSON array of minimal objects for suggestions.
    """
    try:
        from app.services.inventory_search import InventorySearchService
        q = (request.args.get('q') or '').strip()
        inv_type = (request.args.get('type') or '').strip()
        change_type = (request.args.get('change_type') or '').strip()
        results = InventorySearchService.search_inventory_items(
            query_text=q,
            inventory_type=inv_type if inv_type else None,
            organization_id=current_user.organization_id,
            change_type=change_type,
            limit=20
        )
        return jsonify({'results': results})
    except Exception as e:
        logger.exception('Inventory search failed')
        return jsonify({'results': [], 'error': str(e)}), 500

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
            'ownership': getattr(item, 'ownership', None),
            'global_item_name': getattr(getattr(item, 'global_item', None), 'name', None),
            'category_id': getattr(item, 'category_id', None),
            'density': item.density,
            'is_perishable': bool(item.is_perishable),
            'shelf_life_days': item.shelf_life_days,
            'capacity': getattr(item, 'capacity', None),
            'capacity_unit': getattr(item, 'capacity_unit', None),
            'container_material': getattr(item, 'container_material', None),
            'container_type': getattr(item, 'container_type', None),
            'container_style': getattr(item, 'container_style', None),
            'container_color': getattr(item, 'container_color', None),
            'notes': ''
        })
    except Exception as e:
        logger.exception('Failed to load inventory item for edit modal')
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/global-link/<int:item_id>', methods=['POST'])
@login_required
@permission_required('inventory.edit')
def api_toggle_global_link(item_id: int):
    """Link/unlink (soft) an inventory item to its GlobalItem.

    This does NOT clear global_item_id on unlink; it only switches ownership to 'org'
    so the user can edit local specs while retaining a relinkable source.

    JSON: { action: 'unlink'|'relink'|'resync' }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        action = (data.get('action') or '').strip().lower()
        if action not in {'unlink', 'relink', 'resync'}:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400

        query = InventoryItem.query
        if current_user.organization_id:
            query = query.filter_by(organization_id=current_user.organization_id)
        item = query.filter_by(id=item_id).first()
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        if not getattr(item, 'global_item_id', None):
            return jsonify({'success': False, 'error': 'Item is not associated with a global item'}), 400

        gi = db.session.get(GlobalItem, int(item.global_item_id))
        if not gi:
            return jsonify({'success': False, 'error': 'Global item not found'}), 404

        # Prevent cross-type mismatch
        if gi.item_type != item.type:
            return jsonify({'success': False, 'error': 'Global item type does not match inventory item type'}), 400

        from app.services.global_item_sync_service import GlobalItemSyncService

        if action == 'unlink':
            item.ownership = 'org'
            db.session.add(
                UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type='unlink_global',
                    quantity_change=0.0,
                    unit=item.unit or 'count',
                    notes=f"Unlinked from GlobalItem '{gi.name}' (source retained for relink)",
                    created_by=getattr(current_user, 'id', None),
                    organization_id=item.organization_id,
                )
            )
        elif action == 'relink':
            GlobalItemSyncService.relink_inventory_item(item, gi)
            db.session.add(
                UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type='relink_global',
                    quantity_change=0.0,
                    unit=item.unit or 'count',
                    notes=f"Relinked to GlobalItem '{gi.name}'",
                    created_by=getattr(current_user, 'id', None),
                    organization_id=item.organization_id,
                )
            )
        elif action == 'resync':
            # Keep linked, re-apply global specs. (Unit is preserved if user chose a different one.)
            GlobalItemSyncService.relink_inventory_item(item, gi)
            db.session.add(
                UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type='sync_global',
                    quantity_change=0.0,
                    unit=item.unit or 'count',
                    notes=f"Re-synced from GlobalItem '{gi.name}'",
                    created_by=getattr(current_user, 'id', None),
                    organization_id=item.organization_id,
                )
            )

        db.session.commit()

        return jsonify(
            {
                'success': True,
                'item': {
                    'id': item.id,
                    'global_item_id': item.global_item_id,
                    'global_item_name': getattr(gi, 'name', None),
                    'ownership': getattr(item, 'ownership', None),
                },
            }
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to toggle global link")
        return jsonify({'success': False, 'error': str(exc)}), 500

@inventory_bp.route('/api/quick-create', methods=['POST'])
@login_required
def api_quick_create_inventory():
    """JSON endpoint to quickly create an inventory item (zero qty) and return it.
    Uses existing create_inventory_item service. Org-scoped.
    Expected JSON:
      { name, type, unit?, global_item_id?, category_id?/ref_*, density?, capacity?, capacity_unit? }
    """
    try:
        # Validate CSRF token from header
        csrf_token = request.headers.get('X-CSRFToken')
        if not csrf_token:
            return jsonify({'success': False, 'error': 'CSRF token missing'}), 400

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
@permission_required('inventory.view')
def list_inventory():
    inventory_type = request.args.get('type')
    raw_search = (request.args.get('search') or '').strip()
    category_filter = request.args.get('category')
    show_archived = request.args.get('show_archived') == 'true'
    show_zero_qty = request.args.get('show_zero_qty', 'true') == 'true'  # Show zero quantity by default
    normalized_search = raw_search.lower()
    org_id = getattr(current_user, "organization_id", None)

    filter_params = {
        "type": (inventory_type or "").lower(),
        "search": normalized_search,
        "category": (category_filter or "").strip(),
        "show_archived": show_archived,
        "show_zero_qty": show_zero_qty,
    }

    cache_key = inventory_list_cache_key(org_id, filter_params)
    bypass_cache = should_bypass_cache()
    cache_ttl = current_app.config.get("INGREDIENT_LIST_CACHE_TTL", 120)

    try:
        if bypass_cache:
            cache.delete(cache_key)
    except Exception:
        pass

    units = Unit.scoped().filter(Unit.is_active == True).all()
    categories = IngredientCategory.query.order_by(IngredientCategory.name.asc()).all()

    if not bypass_cache:
        cached_payload = None
        try:
            cached_payload = cache.get(cache_key)
        except Exception:
            cached_payload = None
        if cached_payload:
            cached_items = _hydrate_inventory_items(cached_payload.get("items", []))
            total_value = cached_payload.get("total_value", 0.0)
            return render_template(
                'inventory_list.html',
                inventory_items=cached_items,
                items=cached_items,
                categories=categories,
                total_value=total_value,
                units=units,
                show_archived=show_archived,
                show_zero_qty=show_zero_qty,
                get_global_unit_list=get_global_unit_list,
            )

    query = InventoryItem.query
    if org_id:
        query = query.filter_by(organization_id=org_id)
    query = query.filter(~InventoryItem.type.in_(('product', 'product-reserved')))

    if not show_archived:
        query = query.filter(InventoryItem.is_archived.is_(False))
    if inventory_type:
        query = query.filter_by(type=inventory_type)
    if not show_zero_qty:
        query = query.filter(InventoryItem.quantity > 0)
    if raw_search:
        like_pattern = f"%{raw_search}%"
        query = query.filter(InventoryItem.name.ilike(like_pattern))
    if category_filter:
        try:
            query = query.filter(InventoryItem.category_id == int(category_filter))
        except (TypeError, ValueError):
            pass

    query = query.options(
        selectinload(InventoryItem.category),
        selectinload(InventoryItem.global_item).selectinload(GlobalItem.ingredient_category),
    ).order_by(InventoryItem.name.asc())

    inventory_records = query.all()
    serialized_items, total_value = _serialize_inventory_items(inventory_records)

    try:
        cache.set(
            cache_key,
            {
                "items": serialized_items,
                "total_value": total_value,
            },
            timeout=cache_ttl,
        )
    except Exception:
        pass

    hydrated_items = _hydrate_inventory_items(serialized_items)

    return render_template(
        'inventory_list.html',
        inventory_items=hydrated_items,
        items=hydrated_items,
        categories=categories,
        total_value=total_value,
        units=units,
        show_archived=show_archived,
        show_zero_qty=show_zero_qty,
        get_global_unit_list=get_global_unit_list,
    )

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

    if not item:
        flash('Inventory item not found or access denied.', 'error')
        return redirect(url_for('inventory.list_inventory'))

    # Calculate freshness and expired quantities for this item (same as list_inventory)
    from ...blueprints.expiration.services import ExpirationService
    from sqlalchemy import and_

    item.freshness_percent = ExpirationService.get_weighted_average_freshness(item.id)

    # Calculate expired quantity using only InventoryLot (lots handle FIFO tracking now)
    if item.is_perishable:
        today = TimezoneUtils.utc_now().date()
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
    for entry in history:
        if getattr(entry, 'change_type', None) == 'planned':
            entry.queue_code = _extract_queue_code_from_notes(getattr(entry, 'notes', None))
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
        today = TimezoneUtils.utc_now().date()
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
                         now=datetime.now(timezone.utc),
                         int_to_base36=int_to_base36,
                         fifo_filter=fifo_filter,
                         TimezoneUtils=TimezoneUtils,
                         breadcrumb_items=[
                             {'label': 'Inventory', 'url': url_for('inventory.list_inventory')},
                             {'label': item.name}
                         ])

@inventory_bp.route('/add', methods=['POST'])
@login_required
@permission_required('inventory.edit')
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
@permission_required('inventory.adjust')
def adjust_inventory(item_id):
    """Handle inventory adjustments"""
    try:
        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.accept_mimetypes['application/json']
            >= request.accept_mimetypes['text/html']
        )

        def respond(success, message, *, status_code=200, flash_category=None, redirect_url=None):
            if wants_json:
                payload = {'success': success, 'item_id': item_id}
                if success:
                    payload['message'] = message
                else:
                    payload['error'] = message
                return jsonify(payload), status_code
            if flash_category and message:
                flash(message, flash_category)
            return redirect(redirect_url or url_for('.view_inventory', id=item_id))

        item = db.session.get(InventoryItem, int(item_id))
        if not item:
            return respond(
                False,
                "Inventory item not found.",
                status_code=404,
                flash_category="error",
                redirect_url=url_for('.list_inventory'),
            )

        # Authority check
        if not can_edit_inventory_item(item):
            return respond(
                False,
                "Permission denied.",
                status_code=403,
                flash_category="error",
                redirect_url=url_for('.list_inventory'),
            )

        # Extract and validate form data
        form_data = request.form
        logger.info(f"ADJUST INVENTORY - Item: {item.name} (ID: {item_id})")

        # Validate required fields
        change_type = form_data.get('change_type', '').strip().lower()
        if not change_type:
            return respond(False, "Adjustment type is required.", status_code=400, flash_category="error")

        try:
            quantity = float(form_data.get('quantity', 0.0))
            if quantity <= 0:
                return respond(False, "Quantity must be greater than 0.", status_code=400, flash_category="error")
        except (ValueError, TypeError):
            return respond(False, "Invalid quantity provided.", status_code=400, flash_category="error")

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
                        return respond(
                            False,
                            "Total cost requires a positive quantity.",
                            status_code=400,
                            flash_category="error",
                        )
                    cost_override = parsed_cost / qty_val
                else:
                    cost_override = parsed_cost
            except (ValueError, TypeError):
                return respond(False, "Invalid cost provided.", status_code=400, flash_category="error")

        custom_expiration_date = form_data.get('custom_expiration_date')
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
            unit=input_unit
        )

        # Flash result and redirect
        if success:
            logger.info(f"Adjustment successful: {message}")
            return respond(True, f'{change_type.title()} completed: {message}', flash_category='success')
        else:
            logger.error(f"Adjustment failed: {message}")
            return respond(False, f'Adjustment failed: {message}', status_code=400, flash_category='error')

    except Exception as e:
        logger.error(f"Error in adjust_inventory route: {str(e)}")
        return respond(False, f'System error during adjustment: {str(e)}', status_code=500, flash_category='error')

@inventory_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@permission_required('inventory.edit')
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
        is_global_locked = (
            getattr(item, 'global_item_id', None) is not None
            and getattr(item, 'ownership', None) == 'global'
        )

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


@inventory_bp.route('/bulk-updates')
@login_required
@permission_required('inventory.edit')
def bulk_inventory_updates():
    query = InventoryItem.query
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)
    query = query.filter(~InventoryItem.type.in_(('product', 'product-reserved')))
    inventory_records = (
        query.filter(InventoryItem.is_archived != True)
        .order_by(InventoryItem.name.asc())
        .limit(750)
        .all()
    )

    inventory_payload = [
        {
            'id': item.id,
            'name': item.name,
            'unit': item.unit,
            'type': item.type,
            'quantity': float(item.quantity or 0),
        }
        for item in inventory_records
    ]
    unit_options = [
        {
            'name': unit.name,
            'symbol': unit.symbol,
            'unit_type': unit.unit_type,
        }
        for unit in (get_global_unit_list() or [])
    ]

    return render_template(
        'inventory/bulk_updates.html',
        inventory_items=inventory_payload,
        unit_options=unit_options,
    )


@inventory_bp.route('/api/bulk-adjustments', methods=['POST'])
@login_required
@permission_required('inventory.edit')
def api_bulk_inventory_adjustments():
    payload = request.get_json() or {}
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return jsonify({'success': False, 'error': 'Organization context required.'}), 400

    service = BulkInventoryService(organization_id=org_id, user=current_user)
    try:
        result = service.submit_bulk_inventory_update(payload.get('lines') or [])
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except BulkInventoryServiceError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Bulk adjustment API failure")
        return jsonify({'success': False, 'error': str(exc)}), 500