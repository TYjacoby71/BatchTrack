from flask import Blueprint, request, render_template, redirect, flash, jsonify, url_for
from flask_wtf.csrf import CSRFProtect
from flask_login import current_user
from models import db, Unit, CustomUnitMapping
from services.unit_conversion import ConversionEngine
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

@conversion_bp.route('/units/<int:unit_id>/delete', methods=['POST'])
def delete_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    if not (unit.is_custom or unit.user_id):
        flash('Cannot delete system units', 'error')
        return redirect(url_for('conversion.manage_units'))

    try:
        # First delete any custom mappings associated with this unit
        CustomUnitMapping.query.filter(
            (CustomUnitMapping.from_unit == unit.name) | 
            (CustomUnitMapping.to_unit == unit.name)
        ).delete()

        # Then delete the unit
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
    units = get_global_unit_list()
    
    # Organize units by type
    units_by_type = {}
    for unit in units:
        if unit.type not in units_by_type:
            units_by_type[unit.type] = []
        units_by_type[unit.type].append(unit)
    
    return render_template('conversion/units.html', units=units, units_by_type=units_by_type)

@conversion_bp.route('/custom-mappings', methods=['GET', 'POST'])
def manage_mappings():
    if request.method == 'POST':
        try:
            from_unit = request.form.get('from_unit', '').strip()
            to_unit = request.form.get('to_unit', '').strip()
            multiplier = request.form.get('multiplier', type=float)

            if not from_unit or not to_unit or not multiplier or multiplier <= 0:
                flash("All fields required and multiplier must be positive", "danger")
                return redirect(url_for('conversion.manage_mappings'))

            from_unit_obj = Unit.query.filter_by(name=from_unit).first()
            to_unit_obj = Unit.query.filter_by(name=to_unit).first()

            if not from_unit_obj or not to_unit_obj:
                flash("Invalid units selected", "danger")
                return redirect(url_for('conversion.manage_mappings'))

            # Create mapping
            mapping = CustomUnitMapping(
                from_unit=from_unit,
                to_unit=to_unit,
                multiplier=multiplier,
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(mapping)
            db.session.commit()
            flash("Mapping added successfully", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating mapping: {str(e)}", "danger")
            logger.error(f"Error creating mapping: {str(e)}")
        return redirect(url_for('conversion.manage_mappings'))

    units = Unit.query.all()
    mappings = CustomUnitMapping.query.all()
    return render_template('conversion/mappings.html', units=units, mappings=mappings)

@conversion_bp.route('/mappings/<int:mapping_id>/delete', methods=['POST'])
def delete_mapping(mapping_id):
    mapping = CustomUnitMapping.query.get_or_404(mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    flash('Mapping deleted successfully', 'success')
    return redirect(url_for('conversion.manage_mappings'))

@conversion_bp.route('/logs')
def view_logs():
    logs = ConversionLog.query.order_by(ConversionLog.timestamp.desc()).all()
    return render_template('conversion/logs.html', logs=logs)