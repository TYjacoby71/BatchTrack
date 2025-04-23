from flask import Blueprint, request, jsonify
from models import db, InventoryItem

quick_add_bp = Blueprint("quick_add", __name__, template_folder='templates')

@quick_add_bp.route('/ingredient', methods=['POST'])
def quick_add_ingredient():
    data = request.get_json()
    name = data.get('name', '').strip()
    unit = data.get('unit', '').strip()

    if not name or not unit:
        return jsonify({"error": "Missing name or unit"}), 400

    # Check for existing
    existing = InventoryItem.query.filter_by(name=name).first()
    if existing:
        return jsonify({"id": existing.id, "name": existing.name, "unit": existing.unit}), 200

    new_item = InventoryItem(name=name, unit=unit, quantity=0.0, cost_per_unit=0.0)
    db.session.add(new_item)
    db.session.commit()

    return jsonify({
        "id": new_item.id,
        "name": new_item.name,
        "unit": new_item.unit
    }), 200