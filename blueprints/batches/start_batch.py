from flask import Blueprint, request, flash, jsonify
from flask_login import login_required, current_user
from models import db, Batch, Recipe, InventoryItem, BatchContainer, BatchIngredient
from datetime import datetime
from sqlalchemy import extract
from services.unit_conversion import ConversionEngine
from services.inventory_adjustment import process_inventory_adjustment

start_batch_bp = Blueprint('start_batch', __name__)

@start_batch_bp.route('/start_batch', methods=['POST'])
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
        batch_type=data.get('batch_type', 'product'),  # Use the selection from plan production
        scale=scale,
        notes=data.get('notes', ''),
        status='in_progress',
        projected_yield=scale * recipe.predicted_yield,
        projected_yield_unit=recipe.predicted_yield_unit
    )

    db.session.add(new_batch)
    db.session.commit()

    # Handle container deduction first (only for product batches)
    container_errors = []
    batch_type = data.get('batch_type', 'product')
    containers_data = data.get('containers', [])

    print(f"DEBUG: batch_type = {batch_type}")
    print(f"DEBUG: containers_data = {containers_data}")

    if batch_type == 'product' and containers_data:
        for container in containers_data:
            container_id = container.get('id')
            quantity = container.get('quantity', 0)

            print(f"DEBUG: Processing container_id={container_id}, quantity={quantity}")

            if container_id and quantity > 0:
                container_item = InventoryItem.query.get(container_id)
                if container_item:
                    print(f"DEBUG: Found container {container_item.name}, current stock: {container_item.quantity}")
                    # Use the inventory adjustment route
                    try:
                        result = process_inventory_adjustment(
                            item_id=container_id,
                            quantity=-quantity,  # Negative for deduction
                            change_type='batch',
                            unit=container_item.unit,
                            notes=f"Used in batch {label_code}",
                            batch_id=new_batch.id,
                            created_by=current_user.id
                        )

                        if result:
                            # Create single BatchContainer record
                            bc = BatchContainer(
                                batch_id=new_batch.id,
                                container_id=container_id,
                                quantity_used=quantity,
                                cost_each=container_item.cost_per_unit
                            )
                            db.session.add(bc)
                            print(f"DEBUG: Successfully deducted {quantity} {container_item.name}")
                        else:
                            container_errors.append(f"Not enough {container_item.name} in stock.")
                            print(f"DEBUG: Failed to deduct - not enough stock")
                    except Exception as e:
                        container_errors.append(f"Error adjusting inventory for {container_item.name}: {str(e)}")
                        print(f"DEBUG: Exception during deduction: {str(e)}")
                else:
                    print(f"DEBUG: Container with ID {container_id} not found")
            else:
                print(f"DEBUG: Skipping container - invalid ID or quantity")

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

            # Use centralized inventory adjustment 
            result = process_inventory_adjustment(
                item_id=ingredient.id,
                quantity=-required_converted,  # Negative for deduction
                change_type='batch',
                unit=ingredient.unit,
                notes=f"Used in batch {label_code}",
                batch_id=new_batch.id,
                created_by=current_user.id
            )

            if not result:
                ingredient_errors.append(f"Not enough {ingredient.name} in stock.")
                continue

            # Create single BatchIngredient record
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

    # Build deduction summary
    deduction_summary = []
    for ing in new_batch.ingredients:
        deduction_summary.append(f"{ing.amount_used} {ing.unit} of {ing.ingredient.name}")
    for cont in new_batch.containers:
        deduction_summary.append(f"{cont.quantity_used} units of {cont.container.name}")

    # Show errors and success messages
    if ingredient_errors or container_errors:
        all_errors = ingredient_errors + container_errors
        flash("Some items were not deducted due to errors: " + ", ".join(all_errors), "warning")

    if deduction_summary:
        deducted_items = ", ".join(deduction_summary)
        flash(f"Batch started successfully. Deducted items: {deducted_items}", "success")
    else:
        flash(f"Batch started successfully. No items deducted (intermediate batch or no containers selected).", "info")

    db.session.commit()
    return jsonify({'batch_id': new_batch.id})