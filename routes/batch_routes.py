from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, InventoryItem, ProductInventory, BatchIngredient, BatchContainer, BatchTimer, ExtraBatchIngredient, ExtraBatchContainer, InventoryHistory
from datetime import datetime
from utils import get_setting
from sqlalchemy import extract
from services.unit_conversion import ConversionEngine
from blueprints.fifo.services import deduct_fifo
import uuid, os
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')

@batches_bp.route('/start_batch', methods=['POST'])
@login_required
def start_batch():
    data = request.get_json()
    recipe = Recipe.query.get_or_404(data['recipe_id'])
    scale = float(data['scale'])

    # Get current year and count of batches for this recipe this year
    current_year = datetime.now().year
    year_batches = Batch.query.filter(
        Batch.recipe_id == recipe.id,
        extract('year', Batch.started_at) == current_year
    ).count()

    label_code = f"{recipe.label_prefix or 'BTH'}-{current_year}-{year_batches + 1:03d}"

    new_batch = Batch(
        recipe_id=recipe.id,
        label_code=label_code,
        batch_type='product',
        scale=scale,
        notes=data.get('notes', ''),
        status='in_progress',
        projected_yield=scale * recipe.predicted_yield,
        projected_yield_unit=recipe.predicted_yield_unit
    )

    db.session.add(new_batch)
    db.session.commit()

    # Handle container deduction first
    container_errors = []
    for container in data.get('containers', []):
        container_id = container.get('id')
        quantity = container.get('quantity', 0)

        if container_id and quantity:
            container_item = InventoryItem.query.get(container_id)
            if container_item:
                success, deductions = deduct_fifo(
                    container_id,
                    quantity,
                    'batch',
                    f"Used in batch {label_code}",
                    batch_id=new_batch.id,
                    created_by=current_user.id
                )

                if success:
                    # Create batch container record for each FIFO deduction
                    for entry_id, deduct_amount, _ in deductions:
                        container_item = InventoryItem.query.get(container_id)
                        bc = BatchContainer(
                            batch_id=new_batch.id,
                            container_id=container_id,
                            quantity_used=deduct_amount,
                            cost_each=container_item.cost_per_unit
                        )
                        db.session.add(bc)
                else:
                    container_errors.append(f"Not enough {container_item.name} in stock.")

    # Deduct ingredient inventory at start of batch
    ingredient_errors = []

    for assoc in recipe.recipe_ingredients:
        ingredient = assoc.inventory_item
        if not ingredient:
            continue

        required_amount = assoc.amount * scale

        try:
            conversion_result = ConversionEngine.convert_units(
                required_amount,
                assoc.unit,
                ingredient.unit,
                ingredient_id=ingredient.id,
                density=ingredient.density or (ingredient.category.default_density if ingredient.category else None)
            )
            required_converted = conversion_result['converted_value']

            # Use consistent FIFO deduction for all ingredients
            success, deductions = deduct_fifo(
                ingredient.id,
                required_converted,
                'batch',
                f"Used in batch {label_code}",
                batch_id=new_batch.id,
                created_by=current_user.id  # Ensure current user ID is passed
            )

            if not success:
                ingredient_errors.append(f"Not enough {ingredient.name} in stock (FIFO).")
                continue

            # Create BatchIngredient records for each FIFO deduction
            for entry_id, deduct_amount in deductions:
                batch_ingredient = BatchIngredient(
                    batch_id=new_batch.id,
                    ingredient_id=ingredient.id,
                    amount_used=deduct_amount,
                    unit=ingredient.unit,
                    cost_per_unit=ingredient.cost_per_unit  # Use current ingredient cost
                )
                db.session.add(batch_ingredient)
        except ValueError as e:
            ingredient_errors.append(f"Error converting units for {ingredient.name}: {str(e)}")

    if ingredient_errors:
        flash("Some ingredients were not deducted due to errors: " + ", ".join(ingredient_errors), "warning")
    else:
        # Build ingredients summary using the new_batch
        deduction_summary = []
        for ing in new_batch.ingredients:
            deduction_summary.append(f"{ing.amount_used} {ing.unit} of {ing.ingredient.name}")
        for cont in new_batch.containers:
            deduction_summary.append(f"{cont.quantity_used} units of {cont.container.name}")

        deducted_items = ", ".join(deduction_summary)
        flash(f"Batch started successfully. Deducted items: {deducted_items}", "success")

    db.session.commit()
    return jsonify({'batch_id': new_batch.id})

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

@batches_bp.route('/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)

    if batch.status != 'in_progress':
        flash("Only in-progress batches can be cancelled.")
        return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

    try:
        # Fetch batch ingredients, containers, and extra ingredients
        batch_ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
        batch_containers = BatchContainer.query.filter_by(batch_id=batch.id).all()
        extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch.id).all()
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch.id).all()

        # Credit batch ingredients back to inventory
        for batch_ing in batch_ingredients:
            ingredient = batch_ing.ingredient
            if ingredient:
                if batch_ing.unit == ingredient.unit:
                    ingredient.quantity += batch_ing.amount_used
                else:
                    ingredient.quantity += batch_ing.amount_used  # You may still want unit conversion logic here
                db.session.add(ingredient)

        # Credit extra ingredients back to inventory
        for extra_ing in extra_ingredients:
            ingredient = extra_ing.ingredient
            if ingredient:
                if extra_ing.unit == ingredient.unit:
                    ingredient.quantity += extra_ing.quantity
                else:
                    ingredient.quantity += extra_ing.quantity  # Using same unit handling as regular ingredients
                db.session.add(ingredient)

        # Credit regular containers back to inventory
        for batch_container in batch_containers:
            container = batch_container.container
            if container:
                container.quantity += batch_container.quantity_used
                db.session.add(container)

        # Credit extra containers back to inventory
        batch_extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch.id).all()
        for extra_container in batch_extra_containers:
            container = extra_container.container
            if container:
                container.quantity += extra_container.quantity_used
                db.session.add(container)

        # Update batch status
        batch.status = 'cancelled'
        batch.cancelled_at = datetime.utcnow()
        db.session.add(batch)
        db.session.commit()

        # Build restoration summary
        restoration_summary = []
        for batch_ing in batch_ingredients:
            ingredient = InventoryItem.query.get(batch_ing.ingredient_id)
            if ingredient:
                restoration_summary.append(f"{batch_ing.amount_used} {batch_ing.unit} of {ingredient.name}")

        for extra_ing in extra_ingredients:
            if extra_ing.ingredient:
                restoration_summary.append(f"{extra_ing.quantity} {extra_ing.unit} of {extra_ing.ingredient.name}")

        for batch_container in batch_containers:
            container = batch_container.container
            if container:
                restoration_summary.append(f"{batch_container.quantity_used} {container.unit} of {container.name}")

        for extra_container in extra_containers:
            container = extra_container.container
            if container:
                restoration_summary.append(f"{extra_container.quantity_used} {container.unit} of {container.name}")

        # Show appropriate message
        settings = get_setting('alerts', {})
        if settings.get('show_inventory_refund', True):
            restored_items = ", ".join(restoration_summary)
            flash(f"Batch cancelled. Restored items: {restored_items}", "success")
        else:
            flash("Batch cancelled successfully", "success")

        # Verify inventory restoration
        for batch_ing in batch_ingredients:
            ingredient = InventoryItem.query.get(batch_ing.ingredient_id)
            if ingredient and ingredient.quantity < 0:
                flash(f"Warning: {ingredient.name} has negative quantity after restoration!", "error")

    except Exception as e:
        db.session.rollback()
        flash(f"Error cancelling batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))
    return redirect(url_for('batches.list_batches'))


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
        success, deductions = deduct_fifo(
            container_item.id,
            needed_amount,
            'batch',
            f'Extra container for batch {batch.label_code}',
            batch_id=batch.id,
            created_by=current_user.id
        )

        if not success:
            errors.append({
                "item": container_item.name,
                "message": "Not enough in stock (FIFO)",
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

            # Check FIFO availability
            success, deductions = deduct_fifo(
                inventory_item.id,
                needed_amount,
                'batch',
                f'Extra ingredient for batch {batch.label_code}',
                batch_id=batch.id,
                created_by=current_user.id
            )

            if not success:
                errors.append({
                    "item": inventory_item.name,
                    "message": "Not enough in stock (FIFO)",
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