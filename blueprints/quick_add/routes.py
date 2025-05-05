from flask import Blueprint, request, jsonify
from models import db, InventoryItem, Unit

quick_add_bp = Blueprint("quick_add", __name__, template_folder='templates')

@quick_add_bp.route('/container', methods=['POST'])
def quick_add_container():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        container = InventoryItem(
            name=data['name'],
            type='container',
            storage_amount=float(data['storage_amount']),
            storage_unit=data['storage_unit'],
            quantity=0
        )

        db.session.add(container)
        db.session.commit()

        return jsonify({
            'id': container.id,
            'name': container.name,
            'storage_amount': container.storage_amount,
            'storage_unit': container.storage_unit
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@quick_add_bp.route('/unit', methods=['POST'])
def quick_add_unit():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        type_ = data.get('type', 'volume').strip()

        if not name:
            return jsonify({'error': 'Name is required'}), 400

        existing = Unit.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': 'Unit already exists'}), 409

        # Set proper base unit and multiplier based on type
        if type_ == 'count':
            base_unit = 'count'
            multiplier = 1.0
        elif type_ == 'weight':
            base_unit = 'gram'
            multiplier = 1.0  # Default to 1 gram
        elif type_ == 'volume':
            base_unit = 'ml'
            multiplier = 1.0  # Default to 1 milliliter
        elif type_ == 'length':
            base_unit = 'cm'
            multiplier = 1.0  # Default to 1 centimeter
        elif type_ == 'area':
            base_unit = 'sqcm'
            multiplier = 1.0  # Default to 1 square centimeter
        else:
            return jsonify({'error': 'Invalid unit type'}), 400

        new_unit = Unit(
            name=name,
            type=type_,
            base_unit=base_unit,
            multiplier_to_base=multiplier,
            is_custom=True
        )
        db.session.add(new_unit)
        db.session.commit()

        return jsonify({
            'name': new_unit.name,
            'type': new_unit.type
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

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

    # Check if unit requires density
    from_unit = Unit.query.filter_by(name=unit).first()
    if from_unit and from_unit.type in ['volume']:
        # Set default water density for volume ingredients
        new_item = InventoryItem(
            name=name, 
            unit=unit, 
            quantity=0.0, 
            cost_per_unit=0.0,
            density=1.0  # Default water density
        )
        message = "Added with default water density (1.0 g/mL). Update if needed."
    else:
        new_item = InventoryItem(name=name, unit=unit, quantity=0.0, cost_per_unit=0.0)
        message = "Added successfully."
        
    db.session.add(new_item)
    db.session.commit()

    return jsonify({
        "id": new_item.id,
        "name": new_item.name,
        "unit": new_item.unit
    }), 200