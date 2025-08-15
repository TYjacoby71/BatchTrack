from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from ...models import db, Batch, Recipe, InventoryItem, BatchIngredient, BatchContainer, ExtraBatchIngredient, ExtraBatchContainer, InventoryHistory, BatchTimer
from datetime import datetime, timedelta
from ...utils import get_setting
from sqlalchemy import extract, func
from ...services.unit_conversion import ConversionEngine
from ..inventory.routes import adjust_inventory
import uuid, os
from werkzeug.utils import secure_filename
from ...services.inventory_adjustment import process_inventory_adjustment

from . import batches_bp
from .start_batch import start_batch_bp
from .cancel_batch import cancel_batch_bp
from .add_extra import add_extra_bp
from .finish_batch import finish_batch_bp

@batches_bp.route('/api/batch-remaining-details/<int:batch_id>')
@login_required
def get_batch_remaining_details(batch_id):
    """Get detailed remaining inventory for a specific batch"""
    try:
        batch = Batch.query.get_or_404(batch_id)

        # Query ProductInventory entries for this batch that have remaining quantity
        remaining_items = ProductInventory.query.filter_by(batch_id=batch_id).filter(
            ProductInventory.quantity > 0
        ).all()

        # Format the response data
        remaining_data = []
        for item in remaining_items:
            remaining_data.append({
                'product_name': item.product.name,
                'variant': item.variant or 'Base',
                'size_label': item.size_label or 'Bulk',
                'quantity': item.quantity,
                'unit': item.unit,
                'batch_id': batch_id,
                'expiration_date': item.expiration_date.strftime('%Y-%m-%d') if item.expiration_date else None
            })

        return jsonify({
            'success': True,
            'batch_label': batch.label_code,
            'remaining_items': remaining_data
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@batches_bp.route('/columns', methods=['POST'])
@login_required
def set_column_visibility():
    columns = request.form.getlist('columns')
    session['visible_columns'] = columns
    flash('Column preferences updated')
    return redirect(url_for('batches.list_batches'))

@batches_bp.route('/')
@login_required
def list_batches():
    page = request.args.get('page', 1, type=int)
    in_progress_page = request.args.get('in_progress_page', 1, type=int)
    completed_page = request.args.get('completed_page', 1, type=int)

    # Set different pagination limits for tables vs cards
    table_per_page = 10
    card_per_page = 8  # 2 rows x 4 columns

    # Default columns to show if user has not set preference
    visible_columns = session.get('visible_columns', ['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])

    # Get filters from request args or session
    status = request.args.get('status') or session.get('batch_filter_status', 'all')
    recipe_id = request.args.get('recipe_id') or session.get('batch_filter_recipe')
    start = request.args.get('start') or session.get('batch_filter_start')
    end = request.args.get('end') or session.get('batch_filter_end')
    sort_by = request.args.get('sort_by') or session.get('batch_sort_by', 'date_desc')

    # Store current filters in session
    session['batch_filter_status'] = status
    session['batch_filter_recipe'] = recipe_id
    session['batch_filter_start'] = start 
    session['batch_filter_end'] = end
    session['batch_sort_by'] = sort_by

    # Build base query with filters (use scoped query for organization filtering)
    base_query = Batch.scoped()

    if status and status != 'all':
        base_query = base_query.filter_by(status=status)

    if recipe_id:
        base_query = base_query.filter_by(recipe_id=recipe_id)
    if start:
        base_query = base_query.filter(Batch.started_at >= start)
    if end:
        base_query = base_query.filter(Batch.started_at <= end)

    # Apply sorting to base query
    def apply_sorting(query, sort_order):
        if sort_order == 'date_asc':
            return query.order_by(Batch.started_at.asc())
        elif sort_order == 'date_desc':
            return query.order_by(Batch.started_at.desc())
        elif sort_order == 'recipe_asc':
            return query.join(Recipe).order_by(Recipe.name.asc())
        elif sort_order == 'recipe_desc':
            return query.join(Recipe).order_by(Recipe.name.desc())
        elif sort_order == 'status_asc':
            return query.order_by(Batch.status.asc())
        else:
            return query.order_by(Batch.started_at.desc())

    # Separate queries for in-progress and completed batches
    in_progress_query = apply_sorting(base_query.filter_by(status='in_progress'), sort_by)
    completed_query = apply_sorting(base_query.filter(Batch.status != 'in_progress'), sort_by)

    # Paginate in-progress batches (use card pagination for card view)
    in_progress_pagination = in_progress_query.paginate(
        page=in_progress_page, 
        per_page=card_per_page, 
        error_out=False
    )
    in_progress_batches = in_progress_pagination.items

    # Paginate completed batches (use table pagination for table view)
    completed_pagination = completed_query.paginate(
        page=completed_page, 
        per_page=table_per_page, 
        error_out=False
    )
    completed_batches = completed_pagination.items

    # Calculate total cost for each batch
    all_batches = in_progress_batches + completed_batches
    for batch in all_batches:
        ingredient_total = sum((ing.quantity_used or 0) * (ing.cost_per_unit or 0) for ing in batch.batch_ingredients)
        container_total = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
        extras_total = sum((e.quantity_used or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients)
        extra_container_total = sum((e.quantity_used or 0) * (e.cost_each or 0) for e in batch.extra_containers)
        batch.total_cost = ingredient_total + container_total + extras_total + extra_container_total

    # Apply cost-based sorting after calculating costs
    if sort_by == 'cost_desc':
        in_progress_batches.sort(key=lambda x: x.total_cost or 0, reverse=True)
        completed_batches.sort(key=lambda x: x.total_cost or 0, reverse=True)
    elif sort_by == 'cost_asc':
        in_progress_batches.sort(key=lambda x: x.total_cost or 0, reverse=False)
        completed_batches.sort(key=lambda x: x.total_cost or 0, reverse=False)

    all_recipes = Recipe.query.order_by(Recipe.name).all()
    from ...models import InventoryItem
    from ...utils.timezone_utils import TimezoneUtils

    return render_template('batches/batches_list.html',
        InventoryItem=InventoryItem, 
        TimezoneUtils=TimezoneUtils,
        batches=all_batches,
        in_progress_batches=in_progress_batches,
        completed_batches=completed_batches,
        in_progress_pagination=in_progress_pagination,
        completed_pagination=completed_pagination,
        all_recipes=all_recipes, 
        visible_columns=visible_columns)

@batches_bp.route('/<batch_identifier>')
@login_required
def view_batch(batch_identifier):
    try:
        print(f"DEBUG: view_batch called with batch_identifier: {batch_identifier}")
        print(f"DEBUG: Current user organization_id: {current_user.organization_id}")

        if batch_identifier.isdigit():
            # Check if batch exists without scoping first for debugging
            batch_exists = Batch.query.filter_by(id=int(batch_identifier)).first()
            print(f"DEBUG: Batch exists (unscoped): {batch_exists is not None}")
            if batch_exists:
                print(f"DEBUG: Batch organization_id: {batch_exists.organization_id}")

            batch = Batch.scoped().filter_by(id=int(batch_identifier)).first_or_404()
        else:
            batch = Batch.scoped().filter_by(label_code=batch_identifier).first_or_404()

        print(f"DEBUG: Found batch: {batch.label_code}, status: {batch.status}")

        if batch.status == 'in_progress':
            print(f"DEBUG: Redirecting to in_progress view")
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

        # Find previous and next batches of the same status
        prev_batch = Batch.scoped().filter(
            Batch.status == batch.status,
            Batch.id < batch.id
        ).order_by(Batch.id.desc()).first()

        next_batch = Batch.scoped().filter(
            Batch.status == batch.status,
            Batch.id > batch.id
        ).order_by(Batch.id.asc()).first()

        print(f"DEBUG: Rendering view_batch.html template for {batch.status} batch")
        try:
            from datetime import datetime
            current_time = datetime.now()
            return render_template('batches/view_batch.html', batch=batch, prev_batch=prev_batch, next_batch=next_batch, current_time=current_time)
        except Exception as e:
            print(f"Error rendering template: {e}")
            raise

    except Exception as e:
        print(f"DEBUG: Error in view_batch: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        flash(f'Error viewing batch: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/<int:batch_id>/update-notes', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    # Use scoped query to ensure user can only access their organization's batches
    batch = Batch.scoped().filter_by(id=batch_id).first_or_404()

    # Validate ownership - only the creator or same organization can modify
    if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
        if request.is_json:
            return jsonify({'error': 'Permission denied'}), 403
        flash("You don't have permission to modify this batch.", "error")
        return redirect(url_for('batches.list_batches'))
    data = request.get_json() if request.is_json else request.form
    batch.notes = data.get('notes', '')
    batch.tags = data.get('tags', '')
    db.session.commit()
    if request.is_json:
        return jsonify({'message': 'Batch updated successfully', 'redirect': url_for('batches.list_batches')})
    return redirect(url_for('batches.list_batches'))

@batches_bp.route('/in-progress/<batch_identifier>')
@login_required
def view_batch_in_progress(batch_identifier):
    if not isinstance(batch_identifier, int):
        batch_identifier = int(batch_identifier)

    print(f"DEBUG: Looking for batch {batch_identifier}")
    print(f"DEBUG: Current user: {current_user.username}, type: {current_user.user_type}")

    # Check if developer is in customer view
    if current_user.user_type == 'developer':
        from flask import session
        selected_org = session.get('dev_selected_org_id')
        print(f"DEBUG: Developer selected org: {selected_org}")

        # Check if batch exists for this organization
        batch_exists = Batch.query.filter_by(id=batch_identifier).first()
        if batch_exists:
            print(f"DEBUG: Batch {batch_identifier} exists, org: {batch_exists.organization_id}")
        else:
            print(f"DEBUG: Batch {batch_identifier} does not exist in database")

    # Use scoped query to ensure user can only access their organization's batches
    batch = Batch.scoped().filter_by(id=batch_identifier).first_or_404()

    # Validate ownership - only the creator or same organization can view in-progress batches
    if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
        flash("You don't have permission to view this batch.", "error")
        return redirect(url_for('batches.list_batches'))

    if batch.status != 'in_progress':
        flash('This batch is no longer in progress and cannot be edited.', 'warning')
        return redirect(url_for('batches.view_batch', batch_identifier=batch_identifier))

    # Find previous and next in-progress batches (use scoped queries)
    prev_batch = Batch.scoped().filter(
        Batch.status == 'in_progress',
        Batch.id < batch.id
    ).order_by(Batch.id.desc()).first()

    next_batch = Batch.scoped().filter(
        Batch.status == 'in_progress',
        Batch.id > batch.id
    ).order_by(Batch.id.asc()).first()

    # Get existing batch data
    ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
    containers = BatchContainer.query.filter_by(batch_id=batch.id).all()
    timers = BatchTimer.query.filter_by(batch_id=batch.id).all()
    if batch.status != 'in_progress':
        flash('This batch is already completed.')
        return redirect(url_for('batches.list_batches'))

    # Recipe data comes through the batch relationship
    recipe = batch.recipe  # Use the relationship

    # Get units for dropdown
    from ...utils.unit_utils import get_global_unit_list
    units = get_global_unit_list()

    # Build cost summary
    # Recalculate batch cost from frozen batch records
    ingredient_total = sum((ing.quantity_used or 0) * (ing.cost_per_unit or 0) for ing in batch.batch_ingredients)
    container_total = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
    batch_cost = round(ingredient_total + container_total, 3)

    # Only pass product_quantity if it exists in the batch
    product_quantity = batch.product_quantity if hasattr(batch, 'product_quantity') else None
    # Only pass batch_cost if ingredients are used

    all_ingredients = InventoryItem.query.filter_by(type='ingredient').order_by(InventoryItem.name).all()
    inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()

    # Get products for finish batch modal - use Product model
    from ...models import Product

    # Get active products for the organization
    products = Product.query.filter_by(
        is_active=True,
        organization_id=current_user.organization_id
    ).all()

    # Calculate container breakdown for finish modal
    container_breakdown = []
    if batch.containers:
        for container_usage in batch.containers:
            container = container_usage.container
            if container.storage_amount and container.storage_unit:
                container_breakdown.append({
                    'container': container,
                    'size_label': f"{container.storage_amount} {container.storage_unit}",
                    'original_used': container_usage.quantity_used or 0
                })

    # Get timers for this batch with organization scoping
    from datetime import timedelta
    from ...utils.timezone_utils import TimezoneUtils

    # Query timers - match batch organization, not user organization
    timers_query = BatchTimer.query.filter_by(batch_id=batch.id, organization_id=batch.organization_id)

    timers = timers_query.all()
    now = TimezoneUtils.utc_now()

    # Debug: Log timer data
    print(f"DEBUG: Found {len(timers)} timers for batch {batch.id} (org: {batch.organization_id})")
    print(f"DEBUG: User org: {current_user.organization_id if current_user.is_authenticated else 'None'}")
    for timer in timers:
        print(f"DEBUG: Timer {timer.id}: name='{timer.name}', status='{timer.status}', duration={timer.duration_seconds}s, org={timer.organization_id}")

    # Check for active timers
    has_active_timers = any(timer.status == 'active' for timer in timers)

    return render_template('batches/batch_in_progress.html',
                         batch=batch,
                         units=units,
                         batch_cost=batch_cost,
                         product_quantity=product_quantity,
                         inventory_items=inventory_items,
                         all_ingredients=all_ingredients,
                         products=products,
                         container_breakdown=container_breakdown,
                         prev_batch=prev_batch,
                         next_batch=next_batch,
                         timers=timers,
                         now=now,
                         has_active_timers=has_active_timers,
                         timedelta=timedelta)

batches_bp.register_blueprint(start_batch_bp, url_prefix='/batches')
batches_bp.register_blueprint(cancel_batch_bp, url_prefix='/batches')
batches_bp.register_blueprint(add_extra_bp, url_prefix='/add-extra')
batches_bp.register_blueprint(finish_batch_bp, url_prefix='/finish-batch')