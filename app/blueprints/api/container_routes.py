from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.services.stock_check.core import UniversalStockCheckService
from app.services.stock_check.types import StockCheckRequest, InventoryCategory
from app.services.batch_integration_service import BatchIntegrationService

container_api_bp = Blueprint('container_api', __name__)

@container_api_bp.route('/available-containers/<int:recipe_id>')
@login_required
def available_containers(recipe_id):
    """Get available containers for recipe using USCS"""
    try:
        scale = float(request.args.get('scale', '1.0'))

        # Use USCS to get container stock check
        uscs = UniversalStockCheckService()

        # Get all containers for the organization
        container_request = StockCheckRequest(
            inventory_category=InventoryCategory.CONTAINER,
            organization_id=current_user.organization_id
        )

        results = uscs.check_stock([container_request])

        available_containers = []
        for result in results:
            if result.status in ['AVAILABLE', 'OK']:
                available_containers.append({
                    "id": result.item_id,
                    "name": result.name,
                    "storage_amount": result.conversion_details.get('storage_capacity', 0),
                    "storage_unit": result.conversion_details.get('storage_unit', 'ml'),
                    "stock_qty": result.available
                })

        # Sort by storage capacity descending
        sorted_containers = sorted(available_containers, key=lambda c: c['storage_amount'], reverse=True)

        return jsonify({"available": sorted_containers})

    except Exception as e:
        return jsonify({"error": f"Container lookup failed: {str(e)}"}), 500

@container_api_bp.route('/containers/available')
@login_required
def get_available_containers():
    """Get all available containers using USCS"""
    try:
        uscs = UniversalStockCheckService()

        container_request = StockCheckRequest(
            inventory_category=InventoryCategory.CONTAINER,
            organization_id=current_user.organization_id
        )

        results = uscs.check_stock([container_request])

        container_data = []
        for result in results:
            container_data.append({
                'id': result.item_id,
                'name': result.name,
                'size': result.conversion_details.get('storage_capacity', 0),
                'unit': result.conversion_details.get('storage_unit', 'ml'),
                'cost_per_unit': float(result.conversion_details.get('cost_per_unit', 0)),
                'stock_amount': float(result.available)
            })

        return jsonify(container_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@container_api_bp.route('/batches/<int:batch_id>/containers', methods=['GET'])
@login_required
def get_batch_containers(batch_id):
    """Get batch containers using batch integration service"""
    try:
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
    """Remove container from batch using batch integration service"""
    try:
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
    """Adjust container using batch integration service"""
    try:
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