from flask import jsonify, request
from flask_login import login_required
from app.utils.permissions import require_permission

from app.services.unit_conversion import ConversionEngine

from .. import drawers_bp


@drawers_bp.route('/retry-operation', methods=['POST'])
@login_required
@require_permission('inventory.view')
def retry_operation():
    """Generic retry mechanism for conversion operations triggered by drawers."""
    data = request.get_json() or {}
    operation_type = data.get('operation_type')
    operation_data = data.get('operation_data', {})

    if operation_type == 'conversion':
        return retry_conversion_operation(operation_data)

    return jsonify({'error': 'Unknown operation type'}), 400


def retry_conversion_operation(data):
    """Retry conversion after fixing the underlying drawer issue."""
    result = ConversionEngine.convert_units(
        amount=float(data.get('amount', 0)),
        from_unit=data.get('from_unit'),
        to_unit=data.get('to_unit'),
        ingredient_id=data.get('ingredient_id'),
    )
    return jsonify(result)
