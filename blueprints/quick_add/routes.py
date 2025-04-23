from flask import Blueprint, request, jsonify
from flask_wtf.csrf import csrf_exempt
from models import db, InventoryItem

quick_add_bp = Blueprint("quick_add", __name__)

@quick_add_bp.route('/quick-add/ingredient', methods=['POST'])
@csrf_exempt
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

    return jsonify({"id": new_item.id, "name": new_item.name, "unit": new_item.unit}), 200

@quick_add_bp.route('/unit', methods=['POST'])
def quick_add_unit():
    data = request.get_json()
    name = data.get('name', '').strip()
    type_ = data.get('type', '').strip()

    if not name or not type_:
        return jsonify({'error': 'Name and type are required.'}), 400

    existing = Unit.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Unit already exists.'}), 409

    new_unit = Unit(
        name=name,
        type=type_,
        base_unit=name,
        multiplier_to_base=1.0,
        discipline_tags="custom",
        custom=True
    )
    db.session.add(new_unit)
    db.session.commit()

    return jsonify({
        'name': new_unit.name,
        'type': new_unit.type
    }), 201