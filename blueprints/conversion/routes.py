from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required
from models import db, Unit, CustomUnitMapping
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
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

    return render_template('conversion/units.html', units=units, units_by_type={})

@conversion_bp.route('/custom-mappings', methods=['GET', 'POST'])
@login_required
def manage_mappings():
    if request.method == 'POST':
        try:
            if request.is_json:
                data = request.get_json()
                csrf_token = data.get('csrf_token')
            else:
                data = request.form
                csrf_token = data.get('csrf_token')

            validate_csrf(csrf_token)
        except ValidationError:
            return jsonify({'error': 'Invalid CSRF token'}), 400

        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        try:
            multiplier = float(data.get('multiplier', 0))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid multiplier value'}), 400

        if not all([from_unit, to_unit, multiplier > 0]):
            return jsonify({'error': 'Missing or invalid required fields'}), 400

        # Verify both units exist
        from_u = Unit.query.filter_by(name=from_unit).first()
        to_u = Unit.query.filter_by(name=to_unit).first()

        if not from_u or not to_u:
            return jsonify({'error': 'One or both units not found'}), 400

        # Create the custom mapping
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            multiplier=multiplier
        )
        db.session.add(mapping)

        # Update the from_unit's base conversion
        from_u.base_unit = to_u.base_unit
        from_u.multiplier_to_base = multiplier * to_u.multiplier_to_base
        db.session.add(from_u)

        db.session.commit()

        if request.is_json:
            return jsonify({'success': True}), 200
        flash('Custom mapping added successfully.', 'success')
        return redirect(url_for('conversion.manage_mappings'))

    mappings = CustomUnitMapping.query.all()
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