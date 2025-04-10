
from flask import Blueprint, request, jsonify
from models import db, Ingredient, InventoryUnit

quick_add_bp = Blueprint('quick_add', __name__)

@quick_add_bp.route('/ingredient', methods=['POST'])
def quick_add_ingredient():
    data = request.get_json()
    name = data.get('name', '').strip()
    unit = data.get('unit', '').strip()

    if not name or not unit:
        return jsonify({'error': 'Name and unit are required.'}), 400

    existing = Ingredient.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Ingredient already exists.'}), 409

    ingredient = Ingredient(name=name, quantity=0.0, unit=unit, cost_per_unit=0.0)
    db.session.add(ingredient)
    db.session.commit()

    return jsonify({
        'id': ingredient.id,
        'name': ingredient.name,
        'unit': ingredient.unit
    }), 201


@quick_add_bp.route('/unit', methods=['POST'])
def quick_add_unit():
    data = request.get_json()
    name = data.get('name', '').strip()
    type_ = data.get('type', '').strip()

    if not name or not type_:
        return jsonify({'error': 'Name and type are required.'}), 400

    existing = InventoryUnit.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Unit already exists.'}), 409

    new_unit = InventoryUnit(name=name, type=type_)
    db.session.add(new_unit)
    db.session.commit()

    return jsonify({
        'name': new_unit.name,
        'type': new_unit.type
    }), 201
