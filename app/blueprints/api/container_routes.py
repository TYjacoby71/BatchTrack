from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import Recipe, InventoryItem, db, Batch, BatchContainer
from app.services.unit_conversion import ConversionEngine
from ...services.batch_container_service import BatchContainerService

container_api_bp = Blueprint('container_api', __name__, url_prefix='/api')

@container_api_bp.route('/debug-containers')
@login_required
def debug_containers():
    try:
        all_containers = InventoryItem.query.filter_by(
            organization_id=current_user.organization_id
        ).all()

        container_debug = []
        for item in all_containers:
            container_debug.append({
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "storage_amount": item.storage_amount,
                "storage_unit": item.storage_unit,
                "quantity": item.quantity
            })

        return jsonify({
            "total_items": len(all_containers),
            "container_items": [c for c in container_debug if c["type"] == "container"],
            "all_items": container_debug
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@container_api_bp.route('/available-containers/<int:recipe_id>')
@login_required
def available_containers(recipe_id):
    try:
        scale = float(request.args.get('scale', '1.0'))

        # Scoped query to current user's organization
        recipe = Recipe.scoped().filter_by(id=recipe_id).first()
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        # Always return available containers for flexibility
        # Container requirement is now determined at batch planning time

        allowed_container_ids = recipe.allowed_containers or []
        predicted_unit = recipe.predicted_yield_unit
        if not predicted_unit:
            return jsonify({"error": "Recipe missing predicted yield unit"}), 400

        in_stock = []

        # Filter containers for this organization only
        containers_query = InventoryItem.query.filter_by(
            type='container',
            organization_id=current_user.organization_id
        )

        print(f"Found {containers_query.count()} containers for organization {current_user.organization_id}")

        for container in containers_query:
            print(f"Processing container: {container.name}, storage_amount: {container.storage_amount}, storage_unit: {container.storage_unit}")

            if allowed_container_ids and container.id not in allowed_container_ids:
                print(f"Container {container.name} not in allowed list: {allowed_container_ids}")
                continue

            try:
                conversion = ConversionEngine.convert_units(
                    container.storage_amount,
                    container.storage_unit,
                    predicted_unit
                )
                print(f"Conversion result for {container.name}: {conversion}")

                if conversion and 'converted_value' in conversion:
                    in_stock.append({
                        "id": container.id,
                        "name": container.name,
                        "storage_amount": conversion['converted_value'],
                        "storage_unit": predicted_unit,
                        "stock_qty": container.quantity
                    })
            except Exception as e:
                print(f"Conversion failed for {container.name}: {e}")
                continue  # silently skip conversion failures

        sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)

        return jsonify({"available": sorted_containers})

    except Exception as e:
        return jsonify({"error": f"Container API failed: {str(e)}"}), 500

@container_api_bp.route('/containers/available')
@login_required
def get_available_containers():
    """Get all available containers with stock information"""
    try:
        containers = InventoryItem.query.filter_by(
            type='container',
            organization_id=current_user.organization_id
        ).all()

        container_data = []
        for container in containers:
            container_data.append({
                'id': container.id,
                'name': container.name,
                'size': getattr(container, 'storage_amount', None),
                'unit': getattr(container, 'storage_unit', None),
                'cost_per_unit': float(container.cost_per_unit or 0),
                'stock_amount': float(container.quantity or 0)
            })

        return jsonify(container_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers', methods=['GET'])
@login_required
def get_batch_containers(batch_id):
    """Get all containers for a batch with summary"""
    try:
        batch = Batch.query.get_or_404(batch_id)
        containers = BatchContainer.query.filter_by(batch_id=batch_id).all()

        container_data = []
        total_capacity = 0
        product_capacity = 0

        for container in containers:
            container_info = {
                'id': container.id,
                'name': container.container_name,
                'quantity': container.quantity_used,
                'reason': getattr(container, 'reason', 'primary_packaging'),
                'one_time_use': getattr(container, 'one_time_use', False),
                'exclude_from_product': getattr(container, 'exclude_from_product', False),
                'capacity': getattr(container, 'total_capacity', 0)
            }
            container_data.append(container_info)
            total_capacity += container_info['capacity']

            if container.is_valid_for_product:
                product_capacity += container_info['capacity']

        summary = {
            'total_containers': len(containers),
            'total_capacity': total_capacity,
            'product_containers': len([c for c in containers if c.is_valid_for_product]),
            'product_capacity': product_capacity,
            'capacity_unit': getattr(batch, 'projected_yield_unit', 'fl oz')
        }

        return jsonify({
            'containers': container_data,
            'summary': summary
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers/<int:container_id>', methods=['DELETE'])
@login_required
def remove_batch_container(batch_id, container_id):
    """Remove a container from a batch"""
    try:
        container = BatchContainer.query.filter_by(id=container_id, batch_id=batch_id).first_or_404()

        # Restore inventory if not one-time use
        if not getattr(container, 'one_time_use', False) and container.container_item_id:
            from ...services.inventory_adjustment import process_inventory_adjustment
            process_inventory_adjustment(
                item_id=container.container_item_id,
                quantity=container.quantity_used,  # Positive to restore
                change_type='batch_correction',
                unit='units',
                notes=f"Restored container from batch {batch_id}",
                batch_id=batch_id,
                created_by=current_user.id
            )

        db.session.delete(container)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Container removed successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers/<int:container_id>/adjust', methods=['POST'])
@login_required
def adjust_batch_container(batch_id, container_id):
    """Adjust container quantity, replace container type, or mark as damaged"""
    try:
        data = request.get_json()
        adjustment_type = data.get('adjustment_type')
        notes = data.get('notes', '')

        batch = Batch.query.get_or_404(batch_id)

        # Check if it's a regular container or extra container
        container_record = BatchContainer.query.filter_by(id=container_id, batch_id=batch_id).first()
        if not container_record:
            from ...models import ExtraBatchContainer
            container_record = ExtraBatchContainer.query.filter_by(id=container_id, batch_id=batch_id).first_or_404()
            is_extra_container = True
        else:
            is_extra_container = False

        if adjustment_type == 'quantity':
            new_total = data.get('new_total_quantity', 0)
            if new_total < 0:
                return jsonify({'success': False, 'message': 'Total quantity cannot be negative'})

            current_qty = container_record.quantity_used
            quantity_difference = new_total - current_qty

            if quantity_difference != 0:
                # Adjust inventory - positive for returns, negative for additional deductions
                from ...services.inventory_adjustment import process_inventory_adjustment
                change_type = 'refunded' if quantity_difference > 0 else 'batch_adjustment'

                process_inventory_adjustment(
                    item_id=container_record.container_id,
                    quantity=quantity_difference,  # Positive for return, negative for deduction
                    change_type=change_type,
                    unit='count',
                    notes=f"Container quantity adjustment for batch {batch.label_code}: {notes}",
                    batch_id=batch_id,
                    created_by=current_user.id
                )

            container_record.quantity_used = new_total

        elif adjustment_type == 'replace':
            new_container_id = data.get('new_container_id')
            new_quantity = data.get('new_quantity', 1)

            if not new_container_id:
                return jsonify({'success': False, 'message': 'New container must be selected'})

            # Return old containers to inventory
            from ...services.inventory_adjustment import process_inventory_adjustment
            process_inventory_adjustment(
                item_id=container_record.container_id,
                quantity=container_record.quantity_used,  # Positive to return
                change_type='refunded',
                unit='count',
                notes=f"Container replacement return for batch {batch.label_code}: {notes}",
                batch_id=batch_id,
                created_by=current_user.id
            )

            # Deduct new containers
            new_container = InventoryItem.query.get_or_404(new_container_id)
            process_inventory_adjustment(
                item_id=new_container_id,
                quantity=-new_quantity,  # Negative for deduction
                change_type='batch',
                unit='count',
                notes=f"Container replacement for batch {batch.label_code}: {notes}",
                batch_id=batch_id,
                created_by=current_user.id
            )

            # Update container record
            container_record.container_id = new_container_id
            container_record.quantity_used = new_quantity
            container_record.cost_each = new_container.cost_per_unit or 0.0

        elif adjustment_type == 'damage':
            damage_quantity = data.get('damage_quantity', 0)
            if damage_quantity <= 0 or damage_quantity > container_record.quantity_used:
                return jsonify({'success': False, 'message': 'Invalid damage quantity'})

            # Check if we have stock to replace damaged containers
            container_item = InventoryItem.query.get(container_record.container_id)
            if container_item.quantity < damage_quantity:
                return jsonify({
                    'success': False, 
                    'message': f'Not enough {container_item.name} in stock to replace damaged containers. Available: {container_item.quantity}, Need: {damage_quantity}'
                })

            # Create extra container record to track the damaged containers  
            from ...models import ExtraBatchContainer
            damaged_record = ExtraBatchContainer(
                batch_id=batch_id,
                container_id=container_record.container_id,
                container_quantity=damage_quantity,
                quantity_used=damage_quantity,
                cost_each=container_record.cost_each,
                reason='damaged',
                organization_id=current_user.organization_id
            )
            db.session.add(damaged_record)

            # Deduct replacement containers from inventory
            from ...services.inventory_adjustment import process_inventory_adjustment
            process_inventory_adjustment(
                item_id=container_record.container_id,
                quantity=-damage_quantity,  # Negative for deduction
                change_type='damaged',
                unit='count',
                notes=f"Replacement containers for damaged units in batch {batch.label_code}: {notes}",
                batch_id=batch_id,
                created_by=current_user.id
            )

            # The original container count stays the same - we're adding extra containers to replace damaged ones

        db.session.commit()
        return jsonify({'success': True, 'message': 'Container adjusted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/validate-yield', methods=['POST'])
@login_required
def validate_batch_yield(batch_id):
    """Validate yield against container capacity"""
    try:
        data = request.get_json()
        estimated_yield = float(data.get('estimated_yield', 0))

        validation = BatchContainerService.validate_yield_vs_capacity(batch_id, estimated_yield)

        return jsonify(validation)

    except Exception as e:
        return jsonify({'error': str(e)}), 500