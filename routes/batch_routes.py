from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, InventoryItem, ProductInventory, BatchIngredient, BatchContainer, BatchTimer, ExtraBatchIngredient, ExtraBatchContainer, InventoryHistory
from datetime import datetime
from utils import get_setting
from sqlalchemy import extract
from services.unit_conversion import ConversionEngine
from blueprints.inventory.routes import adjust_inventory
import uuid, os
from werkzeug.utils import secure_filename
from services.inventory_adjustment import process_inventory_adjustment

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')



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
    per_page = 10

    query = Batch.query.order_by(Batch.started_at.desc())
    # Default columns to show if user has not set preference
    visible_columns = session.get('visible_columns', ['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])

    # Get filters from request args or session
    status = request.args.get('status') or session.get('batch_filter_status')
    recipe_id = request.args.get('recipe_id') or session.get('batch_filter_recipe')
    start = request.args.get('start') or session.get('batch_filter_start')
    end = request.args.get('end') or session.get('batch_filter_end')

    # Store current filters in session
    session['batch_filter_status'] = status
    session['batch_filter_recipe'] = recipe_id
    session['batch_filter_start'] = start 
    session['batch_filter_end'] = end

    if status and status != 'all':
        query = query.filter_by(status=status)

    if recipe_id:
        query = query.filter_by(recipe_id=recipe_id)
    if start:
        query = query.filter(Batch.timestamp >= start)
    if end:
        query = query.filter(Batch.timestamp <= end)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    batches = pagination.items

    # Calculate total cost for each batch including ingredients, containers and extras
    for batch in batches:
        ingredient_total = sum((ing.amount_used or 0) * (ing.cost_per_unit or 0) for ing in batch.ingredients)
        container_total = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
        extras_total = sum((e.quantity or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients)
        extra_container_total = sum((e.quantity_used or 0) * (e.cost_each or 0) for e in batch.extra_containers)
        batch.total_cost = ingredient_total + container_total + extras_total + extra_container_total

    all_recipes = Recipe.query.order_by(Recipe.name).all()
    from models import InventoryItem
    return render_template('batches_list.html',
        InventoryItem=InventoryItem, 
                         batches=batches, 
                         pagination=pagination,
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
        return render_template('view_batch.html', batch=batch)
    except Exception as e:
        app.logger.error(f'Error viewing batch {batch_identifier}: {str(e)}')
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

    if batch.status != 'in_progress':
        flash('This batch is already completed.')
        return redirect(url_for('batches.list_batches'))

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
    return render_template('batch_in_progress.html',
                         batch=batch,
                         units=units,
                         batch_cost=batch_cost,
                         product_quantity=product_quantity,
                         inventory_items=inventory_items,
                         all_ingredients=all_ingredients)




@batches_bp.route('/add-extra/<int:batch_id>', methods=['POST'])
@login_required
def add_extra_to_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    extra_ingredients = data.get("extra_ingredients", [])
    extra_containers = data.get("extra_containers", [])
    errors = []

    # Handle extra containers
    for container in extra_containers:
        container_item = InventoryItem.query.get(container["item_id"])
        if not container_item:
            continue

        needed_amount = float(container["quantity"])
        result = process_inventory_adjustment(
                item_id=container_item.id,
                quantity=-needed_amount,  # Negative for deduction
                change_type='batch',
                unit=container_item.unit,
                notes=f"Extra container for batch {batch.label_code}",
                batch_id=batch.id,
                created_by=current_user.id
            )

        if not result:
            errors.append({
                "item": container_item.name,
                "message": "Not enough in stock",
                "needed": needed_amount,
                "needed_unit": "units"
            })
        else:
            # Use container's current cost
            new_extra = ExtraBatchContainer(
                batch_id=batch.id,
                container_id=container_item.id,
                quantity_used=needed_amount,
                cost_each=container_item.cost_per_unit
            )
            db.session.add(new_extra)

    # Handle extra ingredients 
    for item in extra_ingredients:
        inventory_item = InventoryItem.query.get(item["item_id"])
        if not inventory_item:
            continue

        try:
            # Handle ingredient conversion
            conversion = ConversionEngine.convert_units(
                item["quantity"],
                item["unit"],
                inventory_item.unit,
                ingredient_id=inventory_item.id,
                density=inventory_item.density or (inventory_item.category.default_density if inventory_item.category else None)
            )
            needed_amount = conversion['converted_value']

            # Use centralized inventory adjustment
            result = process_inventory_adjustment(
                item_id=inventory_item.id,
                quantity=-needed_amount,  # Negative for deduction
                change_type='batch',
                unit=inventory_item.unit,
                notes=f"Extra ingredient for batch {batch.label_code}",
                batch_id=batch.id,
                created_by=current_user.id
            )

            if not result:
                errors.append({
                    "item": inventory_item.name,
                    "message": "Not enough in stock", 
                    "needed": needed_amount,
                    "needed_unit": inventory_item.unit
                })
            else:
                # Use current inventory cost
                new_extra = ExtraBatchIngredient(
                    batch_id=batch.id,
                    inventory_item_id=inventory_item.id,
                    quantity=needed_amount,
                    unit=inventory_item.unit,
                    cost_per_unit=inventory_item.cost_per_unit
                )
                db.session.add(new_extra)

        except ValueError as e:
            errors.append({
                "item": inventory_item.name,
                "message": str(e)
            })

    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    db.session.commit()
    return jsonify({"status": "success"})




# Inventory adjustments now handled through FIFO system