from flask import Blueprint, request, flash, jsonify
from flask_login import login_required, current_user
from ...services.batch_service import BatchOperationsService
from app.utils.permissions import role_required

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