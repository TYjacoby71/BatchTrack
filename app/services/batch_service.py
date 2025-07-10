from flask_login import current_user
from app.models import db
from app.services.product_service import ProductService
from app.services.inventory_adjustment import process_inventory_adjustment
from app.blueprints.expiration.services import ExpirationService
from datetime import datetime

class BatchService:

    @staticmethod
    def finalize_product_output(batch, container_overrides, final_quantity):
        """
        Finalize a batch that creates a product output.
        Uses final_quantity as the source of truth for total product creation.
        Uses container_overrides to determine how much goes into containers vs bulk.
        Creates SKUs and credits inventory for each container type + bulk remainder.
        """
        try:
            from app.models import Product, ProductVariant

            # Get the product and variant
            product = Product.query.filter_by(
                id=batch.product_id,
                organization_id=current_user.organization_id
            ).first()

            variant = ProductVariant.query.filter_by(
                id=batch.variant_id,
                product_id=batch.product_id
            ).first()

            if not product or not variant:
                return False, [], "Selected product or variant not found"

            print(f"DEBUG: Starting finalize_product_output for batch {batch.id}")
            print(f"DEBUG: Container overrides: {container_overrides}")
            print(f"DEBUG: Final quantity (SOURCE OF TRUTH): {final_quantity}")

            # Validate container overrides don't exceed original usage
            for container_usage in batch.containers:
                container_id = container_usage.container.id
                original_used = container_usage.quantity_used or 0
                final_qty = container_overrides.get(container_id, original_used)

                if final_qty > original_used:
                    return False, [], f"Cannot use more {container_usage.container.name} containers ({final_qty}) than were originally allocated ({original_used})"

            inventory_entries = []

            # Process containers first - calculate how much volume they will contain
            total_container_volume = 0
            container_allocations = []

            for container_usage in batch.containers:
                container = container_usage.container
                final_qty = container_overrides.get(container.id, container_usage.quantity_used or 0)

                if final_qty > 0:
                    # Calculate container capacity in output units
                    container_capacity = container.container.storage_amount or 1
                    container_unit = container.container.storage_unit or batch.output_unit

                    # Convert if needed
                    from app.services.unit_conversion import ConversionEngine
                    if container_unit != batch.output_unit:
                        conversion = ConversionEngine.convert_units(
                            container_capacity, container_unit, batch.output_unit, product_id=batch.product_id
                        )
                        if conversion['success']:
                            container_capacity = conversion['converted_value']

                    # Total volume this container type will hold
                    container_volume = final_qty * container_capacity
                    total_container_volume += container_volume

                    container_allocations.append({
                        'container': container,
                        'final_qty': final_qty,
                        'container_capacity': container_capacity,
                        'total_volume': container_volume
                    })

            # Validate that containers don't exceed final quantity
            if total_container_volume > final_quantity:
                return False, [], f"Container allocations ({total_container_volume} {batch.output_unit}) exceed final quantity ({final_quantity} {batch.output_unit})"

            # Create SKUs and credit inventory for containers
            for allocation in container_allocations:
                container = allocation['container']
                container_size_label = f"{container.container.storage_amount or 1}{container.container.storage_unit or 'oz'} {container.container.name}"
                
                # Get or create SKU for this product/variant/size combination
                container_sku = ProductService.get_or_create_sku(
                    product_name=product.name,
                    variant_name=variant.name,
                    size_label=container_size_label,
                    unit='count'
                )

                if not container_sku:
                    continue

                # Credit the total volume for this container type using inventory_item_id
                success = process_inventory_adjustment(
                    item_id=container_sku.inventory_item_id,
                    quantity=allocation['total_volume'],
                    change_type='finished_batch',
                    unit='count',
                    notes=f"From batch {batch.label_code} - {allocation['final_qty']} {container.container.name} containers",
                    batch_id=batch.id,
                    created_by=current_user.id,
                    item_type='product',
                    custom_expiration_date=batch.expiration_date,
                    custom_shelf_life_days=batch.shelf_life_days
                )

                if success:
                    inventory_entries.append({
                        'sku_id': container_sku.id,
                        'size_label': container_size_label,
                        'quantity': allocation['total_volume'],
                        'unit': 'count',
                        'container_name': container.container.name,
                        'container_count': allocation['final_qty'],
                        'type': 'container'
                    })
                    print(f"DEBUG: Created {allocation['total_volume']} {batch.output_unit} of {container_size_label}")

            # Handle bulk remainder - FINAL QUANTITY IS SOURCE OF TRUTH
            bulk_remainder = final_quantity - total_container_volume
            if bulk_remainder > 0:
                bulk_sku = ProductService.get_or_create_sku(
                    product_name=product.name,
                    variant_name=variant.name,
                    size_label="Bulk",
                    unit=batch.output_unit or product.base_unit
                )

                if bulk_sku:
                    success = process_inventory_adjustment(
                        item_id=bulk_sku.inventory_item_id,
                        quantity=bulk_remainder,
                        change_type='finished_batch',
                        unit=batch.output_unit,
                        notes=f"From batch {batch.label_code} - Bulk remainder",
                        batch_id=batch.id,
                        created_by=current_user.id,
                        item_type='product',
                        custom_expiration_date=batch.expiration_date,
                        custom_shelf_life_days=batch.shelf_life_days
                    )

                    if success:
                        inventory_entries.append({
                            'sku_id': bulk_sku.id,
                            'size_label': 'Bulk',
                            'quantity': bulk_remainder,
                            'unit': batch.output_unit
                        })
                        print(f"DEBUG: Created {bulk_remainder} {batch.output_unit} of Bulk")

            print(f"DEBUG: Product finalization complete. Total created: {final_quantity} {batch.output_unit}")
            print(f"DEBUG: Breakdown - Containers: {total_container_volume}, Bulk: {bulk_remainder}")
            return True, inventory_entries, None

        except Exception as e:
            print(f"DEBUG: Error in finalize_product_output: {str(e)}")
            return False, [], str(e)

    @staticmethod
    def _process_batch_containers(containers, container_overrides, batch, product, variant, inventory_entries, is_extra=False):
        """
        Process containers and create SKUs for them
        Returns: total_containerized_volume
        """
        total_containerized = 0
        container_type = "extra" if is_extra else "regular"

        for container in containers:
            final_quantity = container_overrides.get(container.container_id, container.quantity_used)
            if final_quantity > 0:
                # Track how much product capacity these containers represent
                container_capacity = (container.container.storage_amount or 1) * final_quantity
                total_containerized += container_capacity

                # Size label is the full container description (e.g., "4oz Glass Jar")
                container_size_label = f"{container.container.storage_amount or 1}{container.container.storage_unit or 'oz'} {container.container.name}"

                # Get or create SKU for this container type - stored as count units
                container_sku = ProductService.get_or_create_sku(
                    product_name=product.name,
                    variant_name=variant.name,
                    size_label=container_size_label,
                    unit='count'  # Containers are always stored as count units
                )

                # Add inventory for containers - quantity is the number of containers (count)
                success = process_inventory_adjustment(
                    item_id=container_sku.id,
                    quantity=final_quantity,  # Number of containers, not capacity
                    change_type='finished_batch',
                    unit='count',
                    notes=f"From batch {batch.label_code} - {final_quantity} {container_type} {container.container.name} containers",
                    batch_id=batch.id,
                    created_by=current_user.id,
                    item_type='product',
                    custom_expiration_date=batch.expiration_date,
                    custom_shelf_life_days=batch.shelf_life_days
                )

                if success:
                    inventory_entries.append({
                        'sku_id': container_sku.id,
                        'quantity': final_quantity,  # Number of containers
                        'container_name': container.container.name,
                        'container_count': final_quantity,
                        'type': f'{container_type}_container'
                    })

        return total_containerized

    @staticmethod
    def finalize_intermediate_output(batch, final_quantity, output_unit):
        """
        Handle intermediate ingredient output finalization for batches
        Returns: (success, error_message)
        """
        try:
            from app.models import InventoryItem

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
                name=batch.recipe.name, 
                type='ingredient', 
                intermediate=True,
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
                    except ValueError:
                        converted_quantity = final_quantity
                        # Update ingredient unit to match new yield
                        ingredient.unit = output_unit
                else:
                    converted_quantity = final_quantity

                # Determine expiration settings
                custom_expiration_date = None
                custom_shelf_life_days = None

                if batch.is_perishable:
                    custom_expiration_date = batch.expiration_date
                    custom_shelf_life_days = batch.shelf_life_days
                elif ingredient.is_perishable and ingredient.shelf_life_days:
                    custom_expiration_date = ExpirationService.calculate_expiration_date(
                        datetime.utcnow(), ingredient.shelf_life_days
                    )
                    custom_shelf_life_days = ingredient.shelf_life_days

                # Add to inventory using centralized adjustment
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=converted_quantity,
                    change_type='finished_batch',
                    unit=ingredient.unit,
                    notes=f"Batch {batch.label_code} completed - {final_quantity} {output_unit} yield",
                    batch_id=batch.id,
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

                # Determine expiration settings
                custom_expiration_date = None
                custom_shelf_life_days = None

                if batch.is_perishable:
                    custom_expiration_date = batch.expiration_date
                    custom_shelf_life_days = batch.shelf_life_days
                elif ingredient.is_perishable and ingredient.shelf_life_days:
                    custom_expiration_date = ExpirationService.calculate_expiration_date(
                        datetime.utcnow(), ingredient.shelf_life_days
                    )
                    custom_shelf_life_days = ingredient.shelf_life_days

                # Add initial stock using centralized adjustment
                process_inventory_adjustment(
                    item_id=ingredient.id,
                    quantity=final_quantity,
                    change_type='finished_batch',
                    unit=output_unit,
                    notes=f"Initial stock from batch {batch.label_code} - {final_quantity} {output_unit} yield",
                    batch_id=batch.id,
                    created_by=current_user.id,
                    cost_override=unit_cost,
                    custom_expiration_date=custom_expiration_date,
                    custom_shelf_life_days=custom_shelf_life_days
                )

            return True, None

        except Exception as e:
            return False, str(e)