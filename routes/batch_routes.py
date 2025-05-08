from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, InventoryItem, ProductInventory, BatchIngredient, BatchContainer, BatchTimer, ExtraBatchIngredient, ExtraBatchContainer
from datetime import datetime
from utils import get_setting
from sqlalchemy import extract
import uuid, os
from werkzeug.utils import secure_filename
from services.unit_conversion import ConversionEngine

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
        status='in_progress'
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
                if container_item.quantity >= quantity:
                    container_item.quantity -= quantity
                    # Create batch container record
                    bc = BatchContainer(
                        batch_id=new_batch.id,
                        container_id=container_id,
                        quantity_used=quantity,
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

            if ingredient.quantity < required_converted:
                ingredient_errors.append(f"Not enough {ingredient.name} in stock.")
            else:
                # Deduct from inventory
                ingredient.quantity -= required_converted
                db.session.add(ingredient)

                # Create BatchIngredient record with frozen cost
                batch_ingredient = BatchIngredient(
                    batch_id=new_batch.id,
                    ingredient_id=ingredient.id,
                    amount_used=required_converted,
                    unit=ingredient.unit,
                    cost_per_unit=ingredient.cost_per_unit
                )
                db.session.add(batch_ingredient)
        except ValueError as e:
            ingredient_errors.append(f"Error converting units for {ingredient.name}: {str(e)}")

    if ingredient_errors:
        flash("Some ingredients were not deducted due to errors: " + ", ".join(ingredient_errors), "warning")
    else:
        flash("Batch started and inventory deducted.", "success")

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

    if status:
        query = query.filter_by(status=status)

    if recipe_id:
        query = query.filter_by(recipe_id=recipe_id)
    if start:
        query = query.filter(Batch.timestamp >= start)
    if end:
        query = query.filter(Batch.timestamp <= end)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    batches = pagination.items
    all_recipes = Recipe.query.order_by(Recipe.name).all()
    return render_template('batches_list.html', 
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
    recipe = Recipe.query.get_or_404(batch.recipe_id)
    batch.recipe_name = recipe.name  # Add recipe name to batch object
    # Get units for dropdown
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
                         recipe=recipe,
                         units=units,
                         batch_cost=batch_cost,
                         product_quantity=product_quantity,
                         inventory_items=inventory_items,
                         all_ingredients=all_ingredients)

@batches_bp.route('/<int:batch_id>/finish', methods=['POST'])
@login_required
def finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    action = request.form.get('action', 'finish')
    output_type = request.form.get('output_type')
    final_quantity = float(request.form.get('final_quantity', 0))
    output_unit = request.form.get('output_unit')
    notes = request.form.get('notes')

    # Update batch details
    batch.batch_type = output_type
    batch.final_quantity = final_quantity
    batch.output_unit = output_unit
    batch.notes = notes

    if output_type == 'product':
        batch.product_id = request.form.get('product_id')
        batch.variant_label = request.form.get('variant_label')

    try:
        # Verify batch can be finished
        if batch.status != 'in_progress':
            flash("Only in-progress batches can be finished.")
            return redirect(url_for('batches.view_batch', batch_identifier=batch.id))

        # Handle inventory crediting based on batch type
        if action == "finish":
            if batch.batch_type == 'ingredient':
                # Credit produced ingredient to inventory
                ingredient = InventoryItem.query.filter_by(name=batch.recipe.name).first()
                if not ingredient:
                    # Create new intermediate ingredient
                    ingredient = InventoryItem(
                        name=batch.recipe.name,
                        quantity=batch.final_quantity,
                        unit=batch.output_unit,
                        type='ingredient',
                        intermediate=True
                    )
                else:
                    ingredient.quantity += batch.final_quantity
                db.session.add(ingredient)
                batch.inventory_credited = True
            elif batch.batch_type == 'product':
                # Credit to product inventory
                product_inv = ProductInventory(
                    product_id=batch.product_id,
                    variant=batch.variant_id,
                    unit=batch.output_unit,
                    quantity=batch.final_quantity,
                    batch_id=batch.id
                )
                db.session.add(product_inv)
                batch.inventory_credited = True

            # Update batch completion status
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()

        # Timer check unless forced
        if not force and action == "finish":
            active_timers = BatchTimer.query.filter_by(batch_id=batch.id, completed=False).all()
            if active_timers:
                flash("This batch has active timers. Complete timers or confirm finish.", "warning")
                return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

        # Save final batch data
        batch.notes = request.form.get("notes", batch.notes)
        batch.tags = request.form.get("tags", batch.tags)
        batch.completed_at = datetime.utcnow()

        # Set status based on action
        if action == "finish":
            batch.status = "completed"
            flash("✅ Batch marked as completed.")
        elif action == "fail":
            batch.status = "failed"
            flash("⚠️ Batch marked as failed.")

        db.session.commit()
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error completing batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))

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
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch.id).all()
        for extra_container in extra_containers:
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


@batches_bp.route('/fail/<int:batch_id>', methods=['POST'])
@login_required
def mark_batch_failed(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if batch.status != 'in_progress':
        flash("Only in-progress batches can be marked as failed.")
        return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

    batch.status = 'failed'
    batch.completed_at = datetime.utcnow()
    db.session.commit()

    flash("Batch marked as failed. Inventory remains deducted.")
    return redirect(url_for('batches.list_batches'))



    data = request.get_json()

    # Save basic batch data
    batch.notes = data.get("notes", batch.notes)
    batch.tags = data.get("tags", batch.tags)
    batch.yield_amount = data.get("yield_amount", batch.yield_amount)
    batch.yield_unit = data.get("yield_unit", batch.yield_unit)

    # Handle ingredients with delta tracking
    existing_ingredients = {bi.ingredient_id: bi for bi in batch.ingredients}
    new_ingredients = data.get("ingredients", [])

    for item in new_ingredients:
        ing_id = item['id']
        new_amt = float(item['amount'])
        new_unit = item['unit']

        if ing_id in existing_ingredients:
            existing = existing_ingredients[ing_id]
            delta = new_amt - existing.amount_used
            existing.amount_used = new_amt
            existing.unit = new_unit
        else:
            delta = new_amt
            bi = BatchIngredient(batch_id=batch.id, ingredient_id=ing_id, amount_used=new_amt, unit=new_unit)
            db.session.add(bi)

        inventory = InventoryItem.query.get(ing_id)
        if inventory:
            inventory.quantity -= delta
            db.session.add(inventory)

    # Handle containers with inventory sync
    existing_containers = {bc.container_id: bc for bc in batch.containers}
    new_containers = data.get("containers", [])

    for item in new_containers:
        cid = item['id']
        qty = int(item['qty'])
        cost_each = float(item.get('cost_each', 0.0))

        if cid in existing_containers:
            existing = existing_containers[cid]
            delta = qty - existing.quantity_used
            existing.quantity_used = qty
            existing.cost_each = cost_each
        else:
            delta = qty
            bc = BatchContainer(batch_id=batch.id, container_id=cid, quantity_used=qty, cost_each=cost_each)
            db.session.add(bc)

        container_item = InventoryItem.query.get(cid)
        if container_item:
            container_item.quantity -= delta
            db.session.add(container_item)

    db.session.commit()
    return jsonify({"message": "Batch saved successfully."})

@batches_bp.route('/finish-with-timers/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def confirm_finish_with_timers(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if request.method == 'POST':
        return redirect(url_for('batches.finish_batch_force', batch_id=batch.id))
    return render_template('confirm_finish_with_timers.html', batch=batch)

@batches_bp.route('/extras-containers/<int:batch_id>', methods=['POST'])
@login_required
def save_extra_containers(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    extras = request.get_json().get("extras", [])
    errors = []

    # First check stock for all containers
    for item in extras:
        container = InventoryItem.query.get(item["container_id"])
        if not container:
            continue

        # Get current used amount for this container
        existing = ExtraBatchContainer.query.filter_by(
            batch_id=batch.id,
            container_id=item["container_id"]
        ).first()
        current_used = existing.quantity_used if existing else 0
        needed_amount = item["quantity"]

        # Add to current used amount
        total_needed = needed_amount + current_used

        # Check if we have enough
        if total_needed > container.quantity:
            errors.append({
                "container": container.name,
                "message": f"Not enough in stock",
                "available": container.quantity,
                "needed": total_needed
            })

    # If any errors, return them
    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    # If all good, save the extras with cost averaging
    for item in extras:
        existing = ExtraBatchContainer.query.filter_by(
            batch_id=batch.id,
            container_id=item["container_id"]
        ).first()

        container = InventoryItem.query.get(item["container_id"])
        new_quantity = item["quantity"]
        new_cost = item.get("cost_per_unit", 0.0)
        
        if existing:
            # Calculate weighted average cost
            total_quantity = existing.quantity_used + new_quantity
            total_cost = (existing.quantity_used * existing.cost_each) + (new_quantity * new_cost)
            average_cost = total_cost / total_quantity if total_quantity > 0 else 0
            
            container.quantity -= new_quantity  # Deduct new quantity
            existing.quantity_used += new_quantity  # Add to existing
            existing.cost_each = average_cost  # Update to weighted average cost
        else:
            new_extra = ExtraBatchContainer(
                batch_id=batch.id,
                container_id=item["container_id"],
                quantity_used=new_quantity,
                cost_each=new_cost
            )
            container.quantity -= new_quantity
            db.session.add(new_extra)

    db.session.commit()
    return jsonify({"status": "success"})

@batches_bp.route('/extras/<int:batch_id>', methods=['POST'])
@login_required
def save_extra_ingredients(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    extras = request.get_json().get("extras", [])
    errors = []

    # First check stock for all ingredients
    for item in extras:
        ingredient = InventoryItem.query.get(item["ingredient_id"])
        if not ingredient:
            continue

        # Get current used amount for this ingredient
        existing = ExtraBatchIngredient.query.filter_by(
            batch_id=batch.id,
            inventory_item_id=item["ingredient_id"]
        ).first()
        current_used = existing.quantity if existing else 0

        try:
            # Convert requested amount to inventory unit
            from services.conversion_wrapper import safe_convert

            conversion = safe_convert(
                item["quantity"],
                item["unit"],
                ingredient.unit,
                ingredient_id=ingredient.id,
                density=ingredient.density or (ingredient.category.default_density if ingredient.category else None)
            )

            if not conversion["ok"]:
                errors.append({
                    "ingredient": ingredient.name,
                    "message": conversion["error"],
                    "type": "conversion"
                })
                continue

            needed_amount = conversion["result"]["converted_value"]

            # Add to current used amount
            total_needed = needed_amount + current_used

            # Check if we have enough
            if total_needed > ingredient.quantity:
                errors.append({
                    "ingredient": ingredient.name,
                    "message": f"Not enough in stock",
                    "available": ingredient.quantity,
                    "available_unit": ingredient.unit,
                    "needed": total_needed,
                    "needed_unit": ingredient.unit
                })

        except ValueError as e:
            errors.append({
                "ingredient": ingredient.name,
                "message": str(e)
            })

    # If any errors, return them
    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    # If all good, save the extras
    for item in extras:
        existing = ExtraBatchIngredient.query.filter_by(
            batch_id=batch.id,
            inventory_item_id=item["ingredient_id"]
        ).first()

        ingredient = InventoryItem.query.get(item["ingredient_id"])
        conversion_result = ConversionEngine.convert_units(
            item["quantity"],
            item["unit"],
            ingredient.unit,
            ingredient_id=ingredient.id,
            density=ingredient.density or (ingredient.category.default_density if ingredient.category else None)
        )
        converted_qty = conversion_result['converted_value']

        new_cost = item.get("cost_per_unit", 0.0)
        
        if existing:
            # Calculate weighted average cost
            total_quantity = existing.quantity + converted_qty
            total_cost = (existing.quantity * existing.cost_per_unit) + (converted_qty * new_cost)
            average_cost = total_cost / total_quantity if total_quantity > 0 else 0
            
            existing.quantity += converted_qty
            existing.cost_per_unit = average_cost
            ingredient.quantity -= converted_qty
        else:
            new_extra = ExtraBatchIngredient(
                batch_id=batch.id,
                inventory_item_id=item["ingredient_id"],
                quantity=converted_qty,
                unit=ingredient.unit,
                cost_per_unit=new_cost
            )
            db.session.add(new_extra)
            ingredient.quantity -= converted_qty

    db.session.commit()
    return jsonify({"status": "success"})

@batches_bp.route('/force-finish/<int:batch_id>')
@login_required
def force_finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)

    # Optional: Warn if no active timers exist
    if all(timer.completed for timer in batch.timers):
        flash("All timers are already completed. Use the normal Finish Batch button.", "info")
        return redirect(url_for('batches.view_batch_in_progress', batch_id=batch.id))

    # Mark batch as finished
    batch.status = 'finished'
    db.session.commit()

    flash("Batch marked complete. Timers ignored.", "warning")
    return redirect(url_for('batches.view_batch', batch_id=batch.id))

@batches_bp.route("/by_product/<int:product_id>/variant/<variant>/size/<size>/unit/<unit>")
@login_required
def view_batches_by_variant(product_id, variant, size, unit):
    """View FIFO-ordered batches for a specific product variant"""
    batches = ProductInventory.query.filter_by(
        product_id=product_id,
        variant_label=variant,
        size_label=size,
        unit=unit
    ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

    return render_template(
        "batches/by_variant.html",
        batches=batches,
        variant=variant,
        size=size,
        unit=unit
    )

def adjust_inventory_deltas(batch_id, new_ingredients, new_containers):
    existing_ings = {bi.ingredient_id: bi for bi in BatchIngredient.query.filter_by(batch_id=batch_id)}
    existing_conts = {bc.container_id: bc for bc in BatchContainer.query.filter_by(batch_id=batch_id)}

    # Handle Ingredients
    for item in new_ingredients:
        ing_id = item['id']
        new_amt = float(item['amount'])
        unit_used = item['unit']

        existing = existing_ings.get(ing_id)
        old_amt = existing.amount_used if existing else 0
        delta = new_amt - old_amt

        inventory = InventoryItem.query.get(ing_id)
        if inventory:
            stock_unit = inventory.unit
            try:
                converted_delta = ConversionEngine.convert(abs(delta), unit_used, stock_unit, density=inventory.category.default_density)
                if delta < 0:
                    inventory.quantity += converted_delta
                else:
                    inventory.quantity -= converted_delta
                db.session.add(inventory)
            except Exception as e:
                print(f"[Conversion Error] Ingredient {ing_id}: {e}")

    # Handle Containers (assumes same unit - count)
    for item in new_containers:
        cid = item['id']
        new_qty = int(item['qty'])
        existing = existing_conts.get(cid)
        old_qty = existing.quantity_used if existing else 0
        delta = new_qty - old_qty

        container = InventoryItem.query.get(cid)
        if container:
            container.quantity -= delta
            db.session.add(container)