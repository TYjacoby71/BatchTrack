from flask import Blueprint, request, render_template, redirect, flash, jsonify
from flask_wtf.csrf import validate_csrf, generate_csrf
from wtforms.validators import ValidationError
from models import db, Unit, CustomUnitMapping
import logging
logger = logging.getLogger(__name__)

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
def manage_mappings():
    logger.info("Request to /custom-mappings received.")
    if request.method == 'POST':
        logger.info("POST to /custom-mappings received.")
        try:
            csrf_token = request.form.get("csrf_token")
            validate_csrf(csrf_token)
            logger.info(f"CSRF token validated: {csrf_token}")
        except ValidationError:
            flash("Invalid CSRF token", "danger")
            return redirect(request.url)

        from_unit = request.form.get("from_unit", "").strip()
        to_unit = request.form.get("to_unit", "").strip()
        try:
            multiplier = float(request.form.get("multiplier", "0"))
        except ValueError:
            flash("Multiplier must be a valid number.", "danger")
            return redirect(request.url)

        logger.info(f"Form keys: {list(request.form.keys())}")
        logger.info(f"from_unit: {from_unit}, to_unit: {to_unit}, multiplier: {multiplier}")

        if not from_unit or not to_unit or multiplier <= 0:
            flash("All fields are required and multiplier must be greater than 0.", "danger")
            return redirect(request.url)

        from_unit_obj = Unit.query.filter_by(name=from_unit).first()
        to_unit_obj = Unit.query.filter_by(name=to_unit).first()

        if not from_unit_obj or not to_unit_obj:
            flash("Units not found in database.", "danger")
            return redirect(request.url)

        from_unit_obj.base_unit = to_unit_obj.base_unit
        from_unit_obj.multiplier_to_base = multiplier * to_unit_obj.multiplier_to_base

        mapping = CustomUnitMapping(from_unit=from_unit, to_unit=to_unit, multiplier=multiplier)
        db.session.add(mapping)
        db.session.add(from_unit_obj)
        db.session.commit()

        flash("Custom mapping added successfully.", "success")
        return redirect(request.url)

    units = Unit.query.all()
    mappings = CustomUnitMapping.query.all()
    return render_template("conversion/mappings.html", units=units, mappings=mappings, csrf_token=generate_csrf())

@conversion_bp.route('/logs')
def view_logs():
    logs = ConversionLog.query.order_by(ConversionLog.timestamp.desc()).all()
    return render_template('conversion/logs.html', logs=logs)