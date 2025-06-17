from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from ...models import Batch, Recipe, Product, InventoryItem, ProductInventory, BatchIngredient, BatchContainer, BatchTimer, ExtraBatchIngredient, ExtraBatchContainer, InventoryHistory
from ...extensions import db
from datetime import datetime
from ....utils import get_setting
from sqlalchemy import extract
from ....services.unit_conversion import ConversionEngine
from ..inventory.routes import adjust_inventory
import uuid, os
from werkzeug.utils import secure_filename
from services.inventory_adjustment import process_inventory_adjustment

batches_bp = Blueprint('batches', __name__, url_prefix='/batches', template_folder='templates')

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

    # Build base query with filters
    base_query = Batch.query

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
        ingredient_total = sum((ing.amount_used or 0) * (ing.cost_per_unit or 0) for ing in batch.ingredients)
        container_total = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
        extras_total = sum((e.quantity or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients)
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
    from app.models import InventoryItem

    return render_template('batches/batches_list.html',
        InventoryItem=InventoryItem, 
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
        if batch_identifier.isdigit():
            batch = Batch.query.get_or_404(int(batch_identifier))
        else:
            batch = Batch.query.filter_by(label_code=batch_identifier).first_or_404()

        if batch.status == 'in_progress':
            return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

        # Find previous and next batches of the same status
        prev_batch = Batch.query.filter(
            Batch.status == batch.status,
            Batch.id < batch.id
        ).order_by(Batch.id.desc()).first()

        next_batch = Batch.query.filter(
            Batch.status == batch.status,
            Batch.id > batch.id
        ).order_by(Batch.id.asc()).first()

        return render_template('batches/view_batch.html', batch=batch, prev_batch=prev_batch, next_batch=next_batch)
    except Exception as e:
        flash('Error viewing batch. Please try again.')
        return redirect(url_for('batches.list_batches'))

@batches_bp.route('/<int:batch_id>/update-notes', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    batch = Batch.query.get_or_404(batch_id)
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
    batch = Batch.query.get_or_404(batch_identifier)

    if batch.status != 'in_progress':
        flash('This batch is no longer in progress and cannot be edited.', 'warning')
        return redirect(url_for('batches.view_batch', batch_identifier=batch_identifier))

    # Find previous and next in-progress batches
    prev_batch = Batch.query.filter(
        Batch.status == 'in_progress',
        Batch.id < batch.id
    ).order_by(Batch.id.desc()).first()

    next_batch = Batch.query.filter(
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
    from datetime import datetime, timedelta
    from utils.unit_utils import get_global_unit_list
    units = get_global_unit_list()

    # Build cost summary-deleted and fixed in template screenshot taken of original code at 5-6-25 11:02 am
    # Recalculate batch cost from frozen batch records
    ingredient_total = sum((ing.amount_used or 0) * (ing.ingredient.cost_per_unit or 0) for ing in batch.ingredients)
    container_total = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
    batch_cost = round(ingredient_total + container_total, 3)

    # Only pass product_quantity if it exists in the batch
    product_quantity = batch.product_quantity if hasattr(batch, 'product_quantity') else None
    # Only pass batch_cost if ingredients are used

    all_ingredients = InventoryItem.query.filter_by(type='ingredient').order_by(InventoryItem.name).all()
    inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()

    # Get products for finish batch modal
    from app.models import Product
    products = Product.query.filter_by(is_active=True).all()

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
                         next_batch=next_batch)