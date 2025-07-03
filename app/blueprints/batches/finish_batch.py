from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, BatchTimer, InventoryItem, ProductSKU, Batch
from datetime import datetime
from ...blueprints.expiration.services import ExpirationService

finish_batch_bp = Blueprint('finish_batch', __name__)

@finish_batch_bp.route('/<int:batch_id>/fail', methods=['POST'])
@login_required
def mark_batch_failed(batch_id):
    """Mark a batch as failed"""
    print(f"DEBUG: mark_batch_failed called with batch_id: {batch_id}")
    print(f"DEBUG: Request method: {request.method}")
    print(f"DEBUG: Request form data: {dict(request.form)}")
    print(f"DEBUG: Current user: {current_user.username if current_user.is_authenticated else 'Anonymous'}")

    try:
        # Use scoped query to ensure user can only access their organization's batches
        batch = Batch.scoped().filter_by(id=batch_id).first_or_404()
        print(f"DEBUG: Found batch: {batch.label_code}, current status: {batch.status}")

        # Validate ownership - only the creator or same organization can modify
        if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
            flash("You don't have permission to modify this batch.", "error")
            return redirect(url_for('batches.list_batches'))

        batch.status = 'failed'
        batch.failed_at = datetime.utcnow()
        batch.status_reason = request.form.get('reason', '')

        db.session.commit()
        print(f"DEBUG: Successfully marked batch {batch.label_code} as failed by user {current_user.id}")

        flash("⚠️ Batch marked as failed. Inventory remains deducted.", "warning")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        print(f"DEBUG: Error in mark_batch_failed: {str(e)}")
        db.session.rollback()
        flash(f"Error marking batch as failed: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch_id))

@finish_batch_bp.route('/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    # Use scoped query to ensure user can only access their organization's batches
    batch = Batch.scoped().filter_by(id=batch_id).first_or_404()

    # Validate ownership - only the creator or same organization can modify
    if batch.created_by != current_user.id and batch.organization_id != current_user.organization_id:
        flash("You don't have permission to modify this batch.", "error")
        return redirect(url_for('batches.list_batches'))

    if not request.form.get('force'):
        active_timers = BatchTimer.query.filter_by(batch_id=batch.id, status='pending').all()
        if active_timers:
            flash("This batch has active timers. Complete timers or force finish.", "warning")
            return redirect(url_for('batches.confirm_finish_with_timers', batch_id=batch.id))

    try:
        # Basic required fields
        output_type = request.form.get('output_type')
        final_quantity_raw = request.form.get('final_quantity', '').strip()
        output_unit = request.form.get('output_unit') or batch.yield_unit

        final_quantity = float(final_quantity_raw)
        if not output_type or final_quantity <= 0:
            raise ValueError("Missing or invalid output type or quantity")

        # Core batch updates
        batch.batch_type = output_type
        batch.final_quantity = final_quantity
        batch.output_unit = output_unit

        # Optional fields
        batch.notes = request.form.get('notes') or batch.notes
        batch.tags = request.form.get('tags') or batch.tags

        # Perishable logic
        batch.is_perishable = request.form.get('is_perishable') == 'on'
        if batch.is_perishable:
            shelf_life_days = request.form.get('shelf_life_days', type=int)
            if not shelf_life_days or shelf_life_days <= 0:
                raise ValueError("Shelf life days required for perishable items")
            batch.shelf_life_days = shelf_life_days
            # Set expiration date if perishable
            # Calculate expiration date if perishable (use completion time as base)
            batch.expiration_date = None
            if batch.is_perishable and shelf_life_days:
                batch.expiration_date = ExpirationService.calculate_expiration_date(
                    datetime.utcnow(), shelf_life_days
                )

        # Output-type specific logic
        if output_type == 'product':
            batch.product_id = request.form.get('product_id')
            batch.variant_label = request.form.get('variant_label')

            # Get container count overrides from form
            container_overrides = {}
            for key, value in request.form.items():
                if key.startswith('container_final_'):
                    container_id = int(key.replace('container_final_', ''))
                    container_overrides[container_id] = int(value)

            # For actual products (not intermediate ingredients), use product inventory service
            if batch.product_id:
                from ...services.product_service import ProductService
                
                # Get the product name from the product_id (which is actually a SKU ID)
                base_sku = ProductSKU.query.filter_by(
                    id=batch.product_id,
                    organization_id=current_user.organization_id
                ).first()
                
                if not base_sku:
                    raise Exception("Selected product not found")
                
                # Get or create the SKU for this product/variant combination
                target_sku = ProductService.get_or_create_sku(
                    product_name=base_sku.product_name,
                    variant_name=batch.variant_label or 'Base',
                    size_label='Bulk',
                    unit=base_sku.unit
                )
                
                # Add inventory using the centralized service
                from ...services.inventory_adjustment import process_inventory_adjustment
                success = process_inventory_adjustment(
                    item_id=target_sku.id,
                    quantity=batch.final_quantity,
                    change_type='finished_batch',
                    unit=target_sku.unit,
                    notes=f"Added from batch {batch.label_code}",
                    batch_id=batch.id,
                    created_by=current_user.id,
                    item_type='sku'
                )
                
                if not success:
                    raise Exception("Failed to add product inventory")

        elif output_type == 'ingredient':
            # For intermediate ingredients, always use batch output units regardless of containers
            # Containers are just production tools, not part of the inventory structure

            # Calculate total cost including all inputs
            total_cost = sum(
                (ing.quantity_used or 0) * (ing.cost_per_unit or 0) for ing in batch.batch_ingredients
            ) + sum(
                (c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers
            ) + sum(
                (e.quantity_used or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients
            ) + sum(
                (e.quantity_used or 0) * (e.cost_each or 0) for e in batch.extra_containers
            )
            unit_cost = total_cost / final_quantity if final_quantity > 0 else 0

            # Find or create intermediate ingredient
            ingredient = InventoryItem.query.filter_by(
                name=batch.recipe.name, type='ingredient', intermediate=True,
                organization_id=current_user.organization_id
            ).first()

            if ingredient:  # Update existing ingredient
                if output_unit != ingredient.unit:
                    # Convert new yield to match existing ingredient's unit
                    from app.services.unit_conversion import ConversionEngine
                    try:
                        conversion = ConversionEngine.convert_units(
                            final_quantity,
                            output_unit,
                            ingredient.unit,
                            ingredient_id=ingredient.id,
                            density=ingredient.density
                        )
                        converted_quantity = conversion['converted_value']
                        flash(f"Converted {final_quantity} {output_unit} to {converted_quantity} {ingredient.unit} for existing ingredient", "info")
                    except ValueError as e:
                        flash(f"Unit conversion error: {str(e)}. Using original units.", "warning")
                        converted_quantity = final_quantity
                        # Update ingredient unit to match new yield
                        ingredient.unit = output_unit
                else:
                    converted_quantity = final_quantity

                # Determine expiration settings - use ingredient's settings if batch is non-perishable
                custom_expiration_date = None
                custom_shelf_life_days = None
                
                if batch.is_perishable:
                    # Use batch expiration settings
                    custom_expiration_date = batch.expiration_date
                    custom_shelf_life_days = batch.shelf_life_days
                elif ingredient.is_perishable and ingredient.shelf_life_days:
                    # Use ingredient's expiration settings when batch isn't perishable
                    custom_expiration_date = ExpirationService.calculate_expiration_date(
                        datetime.utcnow(), ingredient.shelf_life_days
                    )
                    custom_shelf_life_days = ingredient.shelf_life_days

                # Add to inventory using centralized adjustment with finished_batch change_type
                from app.services.inventory_adjustment import process_inventory_adjustment
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=converted_quantity,
                    change_type='finished_batch',  # Use 'finished_batch' for batch completion additions
                    unit=ingredient.unit,
                    notes=f"Batch {batch.label_code} completed - {final_quantity} {output_unit} yield",
                    batch_id=batch.id,  # This should populate the batch relationship
                    created_by=current_user.id,
                    cost_override=unit_cost,
                    custom_expiration_date=custom_expiration_date,
                    custom_shelf_life_days=custom_shelf_life_days
                )
            else:  # Create new intermediate ingredient
                # Copy perishable properties from batch to new ingredient
                ingredient = InventoryItem(
                    name=batch.recipe.name,
                    type='ingredient',
                    intermediate=True,
                    quantity=0,  # Will be set by process_inventory_adjustment
                    unit=output_unit,
                    cost_per_unit=unit_cost,
                    is_perishable=batch.is_perishable,
                    shelf_life_days=batch.shelf_life_days if batch.is_perishable else None,
                    organization_id=current_user.organization_id,
                    is_active=True,
                    is_archived=False
                )
                db.session.add(ingredient)
                db.session.flush()  # Get the ID

                # Determine expiration settings - use ingredient's settings if batch is non-perishable
                custom_expiration_date = None
                custom_shelf_life_days = None
                
                if batch.is_perishable:
                    # Use batch expiration settings
                    custom_expiration_date = batch.expiration_date
                    custom_shelf_life_days = batch.shelf_life_days
                elif ingredient.is_perishable and ingredient.shelf_life_days:
                    # Use ingredient's expiration settings when batch isn't perishable
                    custom_expiration_date = ExpirationService.calculate_expiration_date(
                        datetime.utcnow(), ingredient.shelf_life_days
                    )
                    custom_shelf_life_days = ingredient.shelf_life_days

                # Add initial stock using centralized adjustment with finished_batch change_type
                from app.services.inventory_adjustment import process_inventory_adjustment
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=final_quantity,
                    change_type='finished_batch',  # Use 'finished_batch' for batch completion additions
                    unit=output_unit,
                    notes=f"Initial stock from batch {batch.label_code} - {final_quantity} {output_unit} yield",
                    batch_id=batch.id,  # This should populate the batch relationship
                    created_by=current_user.id,
                    cost_override=unit_cost,
                    custom_expiration_date=custom_expiration_date,
                    custom_shelf_life_days=custom_shelf_life_days
                )

        # Finalize
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        batch.inventory_credited = True

        db.session.commit()
        flash("✅ Batch completed successfully!", "success")
        return redirect(url_for('batches.list_batches'))

    except Exception as e:
        db.session.rollback()
        flash(f"Error completing batch: {str(e)}", "error")
        return redirect(url_for('batches.view_batch_in_progress', batch_identifier=batch.id))