
from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Unit, CustomUnitMapping
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
        data = request.get_json() if request.is_json else request.form
        name = data.get('name')
        unit_type = data.get('type')
        base_unit = data.get('base_unit')
        multiplier = float(data.get('multiplier'))
        if Unit.query.filter_by(name=name).first():
            if request.is_json:
                return jsonify({'error': 'Unit already exists.'}), 400
            flash('Unit already exists.', 'danger')
        else:
            new_unit = Unit(name=name, type=unit_type, base_unit=base_unit, multiplier_to_base=multiplier, user_id=current_user.id)
            db.session.add(new_unit)
            db.session.commit()
            if request.is_json:
                return jsonify({'success': 'Unit added.'})
            flash('Unit added successfully.', 'success')
        return redirect(url_for('conversion.manage_units'))

    units = ConversionEngine.get_units_by_type()
    if request.headers.get('Accept') == 'application/json':
        return jsonify([{'name': u.name, 'type': u.type, 'base_unit': u.base_unit, 'multiplier_to_base': u.multiplier_to_base} for u in units])
    return render_template('conversion/units.html', units=units)

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
