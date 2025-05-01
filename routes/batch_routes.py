from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit, InventoryItem, ProductInventory, BatchIngredient, BatchContainer, BatchTimer
from datetime import datetime
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

    # Deduct inventory at start of batch
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
                ingredient.quantity -= required_converted
                db.session.add(ingredient)
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
    query = Batch.query.order_by(Batch.started_at.desc())
    # Default columns to show if user has not set preference
    visible_columns = session.get('visible_columns', ['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])

    status = request.args.get('status')
    recipe_id = request.args.get('recipe_id')
    start = request.args.get('start')
    end = request.args.get('end')

    if status:
        query = query.filter_by(status=status)

    if recipe_id:
        query = query.filter_by(recipe_id=recipe_id)
    if start:
        query = query.filter(Batch.timestamp >= start)
    if end:
        query = query.filter(Batch.timestamp <= end)

    batches = query.all()
    all_recipes = Recipe.query.order_by(Recipe.name).all()
    return render_template('batches_list.html', batches=batches, all_recipes=all_recipes, visible_columns=visible_columns)

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
    batch.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Batch notes updated.')

    # Redirect based on batch status
    if batch.status == 'in_progress':
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))
    return redirect(url_for('batches.view_batch', batch_identifier=batch_id))

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

    # Build cost summary
    total_cost = 0
    ingredient_costs = []

    for assoc in recipe.recipe_ingredients:
        ingredient = assoc.inventory_item
        used_amount = assoc.amount * batch.scale
        cost_per_unit = getattr(ingredient, 'cost_per_unit', 0) or 0
        line_cost = round(used_amount * cost_per_unit, 2)
        total_cost += line_cost

        ingredient_costs.append({
            'name': ingredient.name,
            'unit': ingredient.unit,
            'used': used_amount,
            'cost_per_unit': cost_per_unit,
            'line_cost': line_cost
        })

    # Only pass product_quantity if it exists in the batch
    product_quantity = batch.product_quantity if hasattr(batch, 'product_quantity') else None
    # Only pass batch_cost if ingredients are used
    batch_cost = round(total_cost, 2) if ingredient_costs else None

    inventory_items = InventoryItem.query.all()
    return render_template('batch_in_progress.html',
                         batch=batch,
                         recipe=recipe,
                         units=units,
                         batch_cost=batch_cost,
                         product_quantity=product_quantity,
                         ingredient_costs=ingredient_costs,
                         inventory_items=inventory_items)

@batches_bp.route('/finish/<int:batch_id>', methods=['POST'])
@login_required
def finish_batch(batch_id, force=False):
    batch = Batch.query.get_or_404(batch_id)
    action = request.form.get('action', 'finish')

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
        # Create credit entries using batch ingredients
        for batch_ing in batch.ingredients:
            ingredient = batch_ing.ingredient
            if ingredient:
                try:
                    # Convert from batch unit to inventory unit using UUCS
                    conversion_result = ConversionEngine.convert_units(
                        batch_ing.amount_used,
                        batch_ing.unit,
                        ingredient.unit,
                        ingredient_id=ingredient.id,
                        density=ingredient.density or (ingredient.category.default_density if ingredient.category else None)
                    )
                    
                    if conversion_result['conversion_type'] == 'error':
                        flash(f"Error converting units for {ingredient.name}", "error")
                        continue
                        
                    # Credit the converted amount back to inventory
                    ingredient.quantity += conversion_result['converted_value']
                    db.session.add(ingredient)
                    
                    flash(f"Credited {conversion_result['converted_value']} {ingredient.unit} of {ingredient.name}", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error crediting {ingredient.name}: {str(e)}", "error")
                    continue

        # Restore containers
        for bc in batch.containers:
            container = bc.container
            if container:
                container.quantity += bc.quantity_used
                db.session.add(container)

        batch.status = 'cancelled'
        batch.cancelled_at = datetime.utcnow()
        db.session.add(batch)
        db.session.commit()

        flash("Batch cancelled and inventory restored successfully.", "success")
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

@batches_bp.route('/<int:batch_id>/save', methods=['POST'])
@login_required
def save_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if batch.status != 'in_progress':
        flash("Only in-progress batches can be saved.")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

    data = request.get_json()

    # Save basic metadata
    batch.notes = data.get("notes")
    batch.tags = data.get("tags")
    batch.yield_amount = data.get("yield_amount")
    batch.yield_unit = data.get("yield_unit")
    batch.final_quantity = data.get("final_quantity")
    batch.output_unit = data.get("output_unit")
    batch.product_id = data.get("product_id")
    batch.variant_id = data.get("variant_id")

    # Track and adjust inventory deltas
    adjust_inventory_deltas(
        batch_id=batch_id,
        new_ingredients=data.get('ingredients', []),
        new_containers=data.get('containers', [])
    )

    # Handle ingredients
    db.session.query(BatchIngredient).filter_by(batch_id=batch_id).delete()
    for ing_data in data.get('ingredients', []):
        ing_id = int(ing_data.get('id'))
        amount = float(ing_data.get('amount', 0))
        unit = ing_data.get('unit', 'count')
        db.session.add(BatchIngredient(
            batch_id=batch_id,
            ingredient_id=ing_id,
            amount_used=amount,
            unit=unit
        ))

    # Handle containers
    db.session.query(BatchContainer).filter_by(batch_id=batch_id).delete()
    for cont_data in data.get('containers', []):
        cont_id = int(cont_data.get('id'))
        qty = int(cont_data.get('qty', 0))
        cost = float(cont_data.get('cost_each', 0))
        db.session.add(BatchContainer(
            batch_id=batch_id,
            container_id=cont_id,
            quantity_used=qty,
            cost_each=cost
        ))

    # Handle timers
    db.session.query(BatchTimer).filter_by(batch_id=batch_id).delete()
    for timer_data in data.get('timers', []):
        name = timer_data.get('name')
        duration = int(timer_data.get('duration_seconds', 0))
        db.session.add(BatchTimer(
            batch_id=batch_id,
            name=name,
            duration_seconds=duration
        ))

    db.session.commit()
    return jsonify({"message": "Batch saved successfully"})

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