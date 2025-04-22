from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Unit, CustomUnitMapping, ConversionLog
from services.unit_conversion import ConversionEngine

conversion_bp = Blueprint('conversion', __name__, template_folder='templates')

@conversion_bp.route('/convert/<float:amount>/<from_unit>/<to_unit>', methods=['GET'])
def convert(amount, from_unit, to_unit):
    ingredient_id = request.args.get('ingredient_id', None)
    density = request.args.get('density', None, type=float)
    try:
        result = ConversionEngine.convert_units(amount, from_unit, to_unit, ingredient_id=ingredient_id, density=density)
        return jsonify({'result': round(result, 2), 'unit': to_unit})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@conversion_bp.route('/units', methods=['GET', 'POST'])
@login_required
def manage_units():
    if request.method == 'POST':
        name = request.form.get('name')
        type = request.form.get('type', 'count')
        base_unit = request.form.get('base_unit', name)
        multiplier = request.form.get('multiplier', 1.0)
        is_custom = bool(request.form.get('is_custom', False)) # Added to handle custom units

        existing_unit = Unit.query.filter_by(name=name).first()
        if existing_unit:
            existing_unit.type = type
            existing_unit.base_unit = base_unit
            existing_unit.multiplier_to_base = float(multiplier)
        else:
            new_unit = Unit(
                name=name,
                type=type,
                base_unit=base_unit,
                multiplier_to_base=float(multiplier),
                is_custom=is_custom # Added is_custom field to Unit model.  Requires database schema update.
            )
            db.session.add(new_unit)
        db.session.commit()

    units = Unit.query.all()
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

    return render_template('conversion/units.html', units=units, units_by_type=units_by_type, mappings=[]) # units.html needs updating to display custom units separately.


@conversion_bp.route('/custom-mappings', methods=['GET', 'POST'])
@login_required
def manage_mappings():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        multiplier = float(data.get('multiplier'))

        mapping = CustomUnitMapping(
            user_id=current_user.id,
            from_unit=from_unit,
            to_unit=to_unit,
            multiplier=multiplier
        )
        db.session.add(mapping)
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