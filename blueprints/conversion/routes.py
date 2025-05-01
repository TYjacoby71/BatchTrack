from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Unit, CustomUnitMapping, ConversionLog
from services.unit_conversion import ConversionEngine

conversion_bp = Blueprint('conversion', __name__, template_folder='templates')

@conversion_bp.route('/convert/<float:amount>/<from_unit>/<to_unit>', methods=['GET'])
def convert(amount, from_unit, to_unit):
    ingredient_id = request.args.get('ingredient_id', type=int)
    density = request.args.get('density', type=float)

    try:
        result = ConversionEngine.convert_units(
            amount,
            from_unit,
            to_unit,
            ingredient_id=ingredient_id,
            density=density
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({
            'converted_value': None,
            'conversion_type': 'error',
            'message': str(e),
            'requires_attention': True
        }), 400

@conversion_bp.route('/units', methods=['GET', 'POST'])
def manage_units():
    from utils.unit_utils import get_global_unit_list
    try:
        units = get_global_unit_list()
    except Exception as e:
        return jsonify({'error': f'Error loading units: {str(e)}'}), 500


    # Handle JSON requests first
    if request.headers.get('Accept') == 'application/json':
        return jsonify([{
            'id': unit.id,
            'name': unit.name,
            'type': unit.type,
            'base_unit': unit.base_unit,
            'multiplier_to_base': unit.multiplier_to_base,
            'is_custom': unit.is_custom
        } for unit in units])

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            type_ = request.form.get('type')
            base_unit = request.form.get('base_unit')
            multiplier = float(request.form.get('multiplier', 1.0))

            unit = Unit(
                name=name,
                type=type_,
                base_unit=base_unit,
                multiplier_to_base=multiplier,
                is_custom=True
            )
            db.session.add(unit)
            db.session.commit()
            flash('Unit added successfully', 'success')
            return redirect(url_for('conversion.manage_units'))
        except Exception as e:
            flash(f'Error adding unit: {str(e)}', 'error')
            return redirect(url_for('conversion.manage_units'))


    mappings = CustomUnitMapping.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    if request.headers.get('Accept') == 'application/json':
        return jsonify([{
            'id': unit.id,
            'name': unit.name,
            'type': unit.type,
            'base_unit': unit.base_unit,
            'multiplier_to_base': unit.multiplier_to_base,
            'is_custom': unit.is_custom # Add is_custom to JSON response
        } for unit in units])
    # Group units by type
    units_by_type = {}
    for unit in units:
        if unit.type not in units_by_type:
            units_by_type[unit.type] = []
        units_by_type[unit.type].append(unit)

    if request.headers.get('Accept') == 'application/json':
        return jsonify([{
            'id': unit.id,
            'name': unit.name,
            'type': unit.type,
            'base_unit': unit.base_unit,
            'multiplier_to_base': unit.multiplier_to_base,
            'is_custom': unit.is_custom
        } for unit in units])
    return render_template('conversion/units.html', units=units, units_by_type=units_by_type, mappings=[])


@conversion_bp.route('/custom-mappings', methods=['GET', 'POST'])
@login_required
def manage_mappings():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            csrf_token = request.headers.get('X-CSRFToken', '')
        else:
            data = request.form
            csrf_token = data.get('csrf_token', '')
            
        if not csrf_token:
            return jsonify({'error': 'CSRF token missing'}), 400
            
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        try:
            multiplier = float(data.get('multiplier', 0))
        except (ValueError, TypeError):
            if request.is_json:
                return jsonify({'error': 'Invalid multiplier value'}), 400
            flash('Invalid multiplier value', 'error')
            return redirect(url_for('conversion.manage_mappings'))

        if not all([from_unit, to_unit, multiplier]):
            if request.is_json:
                return jsonify({'error': 'Missing required fields'}), 400
            flash('All fields are required', 'error')
            return redirect(url_for('conversion.manage_mappings'))

        # Verify both units exist
        from_u = Unit.query.filter_by(name=from_unit).first()
        to_u = Unit.query.filter_by(name=to_unit).first()
        
        # Create units if they don't exist
        if not from_u:
            # Get the base unit from the target unit if it exists
            base_unit = to_u.base_unit if to_u else 'g'
            unit_type = to_u.type if to_u else 'weight'
            
            from_u = Unit(
                name=from_unit,
                type=unit_type,
                base_unit=base_unit,
                multiplier_to_base=multiplier,  # Initial multiplier from mapping
                is_custom=True
            )
            db.session.add(from_u)

        if not to_u:
            to_u = Unit(
                name=to_unit,
                type=from_u.type,
                base_unit=from_u.base_unit,
                multiplier_to_base=1.0,  # Default multiplier
                is_custom=True
            )
            db.session.add(to_u)
            db.session.flush()  # Ensure IDs are generated
            
        # Create the custom mapping
        mapping = CustomUnitMapping(
            user_id=current_user.id,
            from_unit=from_unit,
            to_unit=to_unit,
            multiplier=multiplier
        )
        db.session.add(mapping)

        # Update the from_unit's base conversion based on the mapping
        if to_u.base_unit == to_u.name:
            # Direct mapping to base unit
            from_u.multiplier_to_base = multiplier
        else:
            # Calculate through the target unit's base conversion
            from_u.multiplier_to_base = multiplier * to_u.multiplier_to_base
            
        db.session.add(from_u)

        db.session.commit()

        if request.is_json:
            return jsonify({'success': 'Mapping added.'})
        flash('Custom mapping added successfully.', 'success')
        return redirect(url_for('conversion.manage_mappings'))

    mappings = CustomUnitMapping.query.filter_by(user_id=current_user.id).all()
    if request.headers.get('Accept') == 'application/json':
        return jsonify([{
            'from_unit': m.from_unit,
            'to_unit': m.to_unit,
            'multiplier': m.multiplier
        } for m in mappings])
    return render_template('conversion/mappings.html', mappings=mappings)

@conversion_bp.route('/logs')
@login_required
def view_logs():
    logs = ConversionLog.query.order_by(ConversionLog.timestamp.desc()).all()
    return render_template('conversion/logs.html', logs=logs)