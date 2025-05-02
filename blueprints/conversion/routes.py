from flask import Blueprint, request, render_template, redirect, flash, url_for, jsonify
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from models import db, Unit, CustomUnitMapping
from flask_login import current_user
from services.unit_conversion import ConversionEngine
import logging

logger = logging.getLogger(__name__)

conversion_bp = Blueprint('conversion_bp', __name__, url_prefix='/conversion')

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

@conversion_bp.route('/units/<int:unit_id>/delete', methods=['POST'])
def delete_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    if not (unit.is_custom or unit.user_id):
        flash('Cannot delete system units', 'error')
        return redirect(url_for('conversion.manage_units'))

    try:
        CustomUnitMapping.query.filter(
            (CustomUnitMapping.from_unit == unit.name) |
            (CustomUnitMapping.to_unit == unit.name)
        ).delete()

        db.session.delete(unit)
        db.session.commit()
        logger.info(f"Successfully deleted unit: {unit.name}")
        flash('Unit deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting unit: {str(e)}', 'error')

    return redirect(url_for('conversion.manage_units'))

@conversion_bp.route('/units', methods=['GET', 'POST'])
def manage_units():
    from utils.unit_utils import get_global_unit_list
    
    if request.method == 'POST':
        from_unit = request.form.get("from_unit", "").strip()
        to_unit = request.form.get("to_unit", "").strip()
        try:
            multiplier = float(request.form.get("multiplier", "0"))
        except:
            flash("Multiplier must be a number.", "danger")
            return redirect(url_for('conversion_bp.manage_units'))

        if not from_unit or not to_unit or multiplier <= 0:
            flash("All fields are required.", "danger")
            return redirect(url_for('conversion_bp.manage_units'))

        from_unit_obj = Unit.query.filter_by(name=from_unit).first()
        to_unit_obj = Unit.query.filter_by(name=to_unit).first()

        if not from_unit_obj or not to_unit_obj:
            flash("Units not found in database.", "danger")
            return redirect(url_for('conversion_bp.manage_units'))

        existing = CustomUnitMapping.query.filter_by(
            from_unit=from_unit,
            to_unit=to_unit
        ).first()
        if existing:
            flash("This mapping already exists.", "warning")
            return redirect(url_for('conversion_bp.manage_units'))

        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            multiplier=multiplier,
            user_id=getattr(current_user, "id", None)
        )
        db.session.add(mapping)
        db.session.commit()
        flash("Custom mapping added successfully.", "success")
        return redirect(url_for('conversion_bp.manage_units'))

    units = get_global_unit_list()
    mappings = CustomUnitMapping.query.all()

    units_by_type = {}
    for unit in units:
        if unit.type not in units_by_type:
            units_by_type[unit.type] = []
        units_by_type[unit.type].append(unit)

    return render_template('conversion/units.html', units=units, units_by_type=units_by_type, mappings=mappings)

@conversion_bp.route('/custom-mappings', methods=['POST'])
def manage_mappings():
    try:
        csrf_token = request.form.get("csrf_token")
        validate_csrf(csrf_token)
    except ValidationError:
        flash("Invalid CSRF token", "danger")
        return redirect(url_for('conversion_bp.manage_units'))

    from_unit = request.form.get("from_unit", "").strip()
    to_unit = request.form.get("to_unit", "").strip()
    try:
        multiplier = float(request.form.get("multiplier", "0"))
    except:
        flash("Multiplier must be a number.", "danger")
        return redirect(url_for('conversion_bp.manage_units'))

    if not from_unit or not to_unit or multiplier <= 0:
        flash("All fields are required.", "danger")
        return redirect(url_for('conversion_bp.manage_units'))

    from_unit_obj = Unit.query.filter_by(name=from_unit).first()
    to_unit_obj = Unit.query.filter_by(name=to_unit).first()

    if not from_unit_obj or not to_unit_obj:
        flash("Units not found in database.", "danger")
        return redirect(url_for('conversion_bp.manage_units'))

    existing = CustomUnitMapping.query.filter_by(
        from_unit=from_unit,
        to_unit=to_unit
    ).first()
    if existing:
        flash("This mapping already exists.", "warning")
        return redirect(url_for('conversion_bp.manage_units', _anchor='mappings'))

    mapping = CustomUnitMapping(
        from_unit=from_unit,
        to_unit=to_unit,
        multiplier=multiplier,
        user_id=getattr(current_user, "id", None)
    )
    db.session.add(mapping)
    db.session.commit()
    flash("Custom mapping added successfully.", "success")
    return redirect(url_for('conversion_bp.manage_units'))