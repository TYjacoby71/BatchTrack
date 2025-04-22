from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from models import db, Unit, CustomUnitMapping, ConversionLog
from services.unit_conversion import ConversionEngine

conversion_bp = Blueprint('conversion', __name__, template_folder='templates')

@conversion_bp.route('/convert/<float:amount>/<from_unit>/<to_unit>', methods=['GET'])
def convert(amount, from_unit, to_unit):
    ingredient_id = request.args.get('ingredient_id', None)
    density = request.args.get('density', None, type=float)
    try:
        # Check for custom mapping first
        if current_user.is_authenticated:
            mapping = CustomUnitMapping.query.filter_by(
                user_id=current_user.id,
                from_unit=from_unit,
                to_unit=to_unit
            ).first()

            if mapping:
                result = amount * mapping.multiplier
                return jsonify({
                    'result': round(result, 2),
                    'unit': to_unit,
                    'mapping_used': True,
                    'mapping_multiplier': mapping.multiplier
                })

        # Fall back to standard conversion
        result = ConversionEngine.convert_units(amount, from_unit, to_unit, ingredient_id=ingredient_id, density=density)
        return jsonify({'result': round(result, 2), 'unit': to_unit})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@conversion_bp.route('/units', methods=['GET', 'POST'])
@login_required
def manage_units():
    if request.method == 'POST':
        name = request.form.get('name')
        type = request.form.get('type')
        base_unit = request.form.get('base_unit')
        multiplier = float(request.form.get('multiplier'))

        if not Unit.query.filter_by(name=name).first():
            new_unit = Unit(
                name=name,
                type=type,
                base_unit=base_unit,
                multiplier_to_base=multiplier
            )
            db.session.add(new_unit)
            db.session.commit()
            flash('Unit added successfully!', 'success')
        else:
            flash('Unit already exists!', 'error')

    units = Unit.query.order_by(Unit.type, Unit.name).all()
    mappings = CustomUnitMapping.query.all()
    return render_template('conversion/units.html', units=units, mappings=mappings)

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