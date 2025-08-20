from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import Recipe, InventoryItem, db, Batch, BatchContainer, ExtraBatchContainer
from app.services.stock_check.core import UniversalStockCheckService
from app.services.recipe_service._production_planning import plan_production

container_api_bp = Blueprint('container_api', __name__)

@container_api_bp.route('/debug-containers')
@login_required
def debug_containers():
    """Debug endpoint for container inspection"""
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
    """Get available containers for recipe - delegates to production planning service"""
    try:
        scale = float(request.args.get('scale', '1.0'))
        
        # Use production planning service which leverages stock check system
        planning_result = plan_production(recipe_id, scale)
        
        if not planning_result.get('success', True):
            return jsonify({"error": planning_result.get('error', 'Planning failed')}), 400
            
        # Extract container availability from stock check results
        stock_results = planning_result.get('stock_check', [])
        available_containers = []
        
        for result in stock_results:
            if result.get('type') == 'container' and result.get('status') in ['AVAILABLE', 'OK']:
                # Get container details from conversion_details
                conversion_details = result.get('conversion_details', {})
                available_containers.append({
                    "id": result['item_id'],
                    "name": result['name'],
                    "storage_amount": conversion_details.get('storage_capacity', 0),
                    "storage_unit": conversion_details.get('storage_unit', 'ml'),
                    "stock_qty": result['available']
                })
        
        # Sort by storage capacity descending
        sorted_containers = sorted(available_containers, key=lambda c: c['storage_amount'], reverse=True)
        
        return jsonify({"available": sorted_containers})

    except Exception as e:
        return jsonify({"error": f"Container API failed: {str(e)}"}), 500

@container_api_bp.route('/containers/available')
@login_required
def get_available_containers():
    """Get all available containers with stock information - delegates to stock check service"""
    try:
        from app.services.stock_check.handlers.container_handler import ContainerHandler
        
        containers = InventoryItem.query.filter_by(
            type='container',
            organization_id=current_user.organization_id
        ).all()

        container_handler = ContainerHandler()
        container_data = []
        
        for container in containers:
            details = container_handler.get_item_details(container.id)
            if details:
                container_data.append({
                    'id': details['id'],
                    'name': details['name'],
                    'size': details['storage_amount'],
                    'unit': details['storage_unit'],
                    'cost_per_unit': float(details['cost_per_unit'] or 0),
                    'stock_amount': float(details['quantity'] or 0)
                })

        return jsonify(container_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers', methods=['GET'])
@login_required
def get_batch_containers(batch_id):
    """Get all containers for a batch with summary - delegates to batch service"""
    try:
        from app.services.batch_integration_service import BatchIntegrationService
        
        # Use batch service to get container summary
        batch_service = BatchIntegrationService()
        result = batch_service.get_batch_containers_summary(batch_id)
        
        if not result.get('success'):
            return jsonify({'error': result.get('error', 'Failed to get containers')}), 400
            
        return jsonify(result['data'])

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers/<int:container_id>', methods=['DELETE'])
@login_required
def remove_batch_container(batch_id, container_id):
    """Remove a container from a batch - delegates to batch service"""
    try:
        from app.services.batch_integration_service import BatchIntegrationService
        
        batch_service = BatchIntegrationService()
        result = batch_service.remove_container_from_batch(batch_id, container_id)
        
        if result.get('success'):
            return jsonify({'success': True, 'message': 'Container removed successfully'})
        else:
            return jsonify({'success': False, 'message': result.get('error', 'Failed to remove container')}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers/<int:container_id>/adjust', methods=['POST'])
@login_required
def adjust_batch_container(batch_id, container_id):
    """Adjust container quantity, replace container type, or mark as damaged - delegates to batch service"""
    try:
        from app.services.batch_integration_service import BatchIntegrationService
        
        data = request.get_json()
        batch_service = BatchIntegrationService()
        
        result = batch_service.adjust_batch_container(
            batch_id=batch_id,
            container_id=container_id,
            adjustment_type=data.get('adjustment_type'),
            adjustment_data=data
        )
        
        if result.get('success'):
            return jsonify({'success': True, 'message': result.get('message', 'Container adjusted successfully')})
        else:
            return jsonify({'success': False, 'message': result.get('error', 'Failed to adjust container')}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500