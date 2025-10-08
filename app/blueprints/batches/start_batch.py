from flask import Blueprint, request, flash, jsonify
from flask_login import login_required, current_user
from ...services.batch_service import BatchOperationsService
from app.utils.permissions import role_required
from app.utils.permissions import require_permission

start_batch_bp = Blueprint('start_batch', __name__)

@start_batch_bp.route('/start_batch', methods=['POST'])
@login_required
def start_batch():
    """Start a new batch - thin controller delegating to service"""
    try:
        # Get request data
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        batch_type = data.get('batch_type', 'ingredient')
        notes = data.get('notes', '')
        containers_data = data.get('containers', [])
        requires_containers = data.get('requires_containers', False)
        portioning_data = data.get('portioning_data')

        # 🔍 COMPREHENSIVE PORTIONING DEBUG
        print(f"🔍 START_BATCH DEBUG: Full request payload: {data}")
        print(f"🔍 START_BATCH DEBUG: Raw portioning_data from request: {portioning_data}")
        print(f"🔍 START_BATCH DEBUG: Type of portioning_data: {type(portioning_data)}")
        
        if portioning_data:
            print(f"🔍 START_BATCH DEBUG: Portioning data keys: {list(portioning_data.keys()) if isinstance(portioning_data, dict) else 'NOT A DICT'}")
            if isinstance(portioning_data, dict):
                for key, value in portioning_data.items():
                    print(f"🔍 START_BATCH DEBUG: portioning_data[{key}] = {value} (type: {type(value)})")
        else:
            print("🔍 START_BATCH DEBUG: No portioning_data in request")

        # Check if batch_data contains portioning info as fallback
        batch_data = data.get('batch_data')
        if batch_data and isinstance(batch_data, dict):
            batch_portioning = batch_data.get('portioning_data')
            print(f"🔍 START_BATCH DEBUG: batch_data.portioning_data: {batch_portioning}")
            if batch_portioning and not portioning_data:
                print("🔍 START_BATCH DEBUG: Using portioning_data from batch_data as fallback")
                portioning_data = batch_portioning

        # Delegate to service
        batch, errors = BatchOperationsService.start_batch(
            recipe_id=recipe_id,
            scale=scale,
            batch_type=batch_type,
            notes=notes,
            containers_data=containers_data,
            requires_containers=requires_containers,
            portioning_data=portioning_data
        )

        if not batch:
            # If batch is None, errors contains the error message
            flash(f"Failed to start batch: {', '.join(errors)}", "error")
            return jsonify({'error': 'Failed to start batch'}), 400

        if errors:
            # Batch was created but with warnings
            flash(f"Batch started with warnings: {', '.join(errors)}", "warning")
        else:
            # Build success message
            deduction_summary = []
            for ing in batch.batch_ingredients:
                deduction_summary.append(f"{ing.quantity_used} {ing.unit} of {ing.inventory_item.name}")
            for cont in batch.containers:
                deduction_summary.append(f"{cont.quantity_used} units of {cont.container.name}")

            if deduction_summary:
                deducted_items = ", ".join(deduction_summary)
                flash(f"Batch started successfully. Deducted items: {deducted_items}", "success")
            else:
                flash("Batch started successfully", "success")

        return jsonify({'batch_id': batch.id})

    except Exception as e:
        flash(f"Error starting batch: {str(e)}", "error")
        return jsonify({'error': str(e)}), 500