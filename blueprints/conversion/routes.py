from flask import Blueprint, request, render_template, redirect, flash, jsonify, url_for
from flask_wtf.csrf import CSRFProtect
from flask_login import current_user
from models import db, Unit, CustomUnitMapping

csrf = CSRFProtect()
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
    try:
        units = get_global_unit_list()
        custom_units = [unit for unit in units if unit.is_custom]
        logger.info(f"Found custom units: {[(unit.name, unit.type, unit.user_id) for unit in custom_units]}")
    except Exception as e:
        logger.error(f"Error loading units: {str(e)}")
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
            name = request.form.get('name', '').strip()
            type_ = request.form.get('type', '').strip()

            if not name or not type_:
                flash('Name and type are required', 'error')
                return redirect(url_for('conversion.manage_units'))

            # First check if unit exists
            existing_unit = Unit.query.filter_by(name=name).first()
            if existing_unit:
                flash('Unit already exists', 'error')
                return redirect(url_for('conversion.manage_units'))

            # Set base unit based on type
            if type_ == 'count':
                base_unit = 'count'
            elif type_ == 'weight':
                base_unit = 'gram'
            elif type_ == 'volume':
                base_unit = 'ml'
            elif type_ == 'length':
                base_unit = 'cm'
            elif type_ == 'area':
                base_unit = 'sqcm'
            else:
                flash('Invalid unit type', 'error')
                return redirect(url_for('conversion.manage_units'))

            # Always start with multiplier 1.0
            multiplier = 1.0

            unit = Unit(
                name=name,
                type=type_,
                base_unit=base_unit,
                multiplier_to_base=multiplier,
                is_custom=True,
                user_id=current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None
            )
            db.session.add(unit)
            db.session.commit()
            flash(f'Unit "{name}" added successfully. Remember to define a custom mapping if needed!', 'info')
            return redirect(url_for('conversion.manage_units'))
        except Exception as e:
            flash(f'Error adding unit: {str(e)}', 'error')
            return redirect(url_for('conversion.manage_units'))

    return render_template('conversion/units.html', units=units, units_by_type={})

@conversion_bp.route('/custom-mappings', methods=['GET', 'POST'])
def manage_mappings():
    if request.method == 'POST':
        from_unit = request.form.get('from_unit', '').strip()
        to_unit = request.form.get('to_unit', '').strip()
        multiplier = request.form.get('multiplier', type=float)
        
        if not from_unit or not to_unit or not multiplier or multiplier <= 0:
            flash("All fields are required and multiplier must be positive", "danger")
            return redirect(url_for('conversion.manage_mappings'))

        logger.info(f"Form keys: {list(request.form.keys())}")
        logger.info(f"from_unit: {from_unit}, to_unit: {to_unit}, multiplier: {multiplier}")

        if not from_unit or not to_unit or multiplier <= 0:
            flash("All fields are required and multiplier must be greater than 0.", "danger")
            return redirect(request.url)

        # Validate units exist and check type consistency
        from_unit_obj = Unit.query.filter_by(name=from_unit).first()
        to_unit_obj = Unit.query.filter_by(name=to_unit).first()

        if not from_unit_obj or not to_unit_obj:
            flash(f"Units not found: {from_unit if not from_unit_obj else to_unit}", "danger")
            return redirect(request.url)

        # Prevent circular mappings
        existing_mappings = CustomUnitMapping.query.all()
        def check_circular(start, current, visited=None):
            if visited is None:
                visited = set()
            if current in visited:
                return True
            visited.add(current)
            for mapping in existing_mappings:
                if mapping.from_unit == current:
                    if check_circular(start, mapping.to_unit, visited):
                        return True
            return False

        if check_circular(from_unit, to_unit):
            error_msg = "Circular unit mapping detected"
            if request.is_json:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, "danger")
            return redirect(request.url)

        # Validate unit type consistency
        if from_unit_obj.type != to_unit_obj.type and not (
            {'volume', 'weight'} >= {from_unit_obj.type, to_unit_obj.type}
        ):
            error_msg = f"Cannot create mapping between different unit types: {from_unit_obj.type} and {to_unit_obj.type}"
            if request.is_json:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, "danger")
            return redirect(request.url)

        # Create custom mapping without modifying original units
        # Create custom mapping
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            multiplier=multiplier,
            user_id=current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None
        )
        db.session.add(mapping)
        
        # Update the custom unit's multiplier_to_base
        custom_unit = Unit.query.filter_by(name=from_unit).first()
        if custom_unit and custom_unit.is_custom:
            custom_unit.multiplier_to_base = multiplier
        
        db.session.commit()
        flash("Custom mapping added successfully.", "success")
        return redirect(request.url)

@conversion_bp.route('/mappings/<int:mapping_id>/delete', methods=['POST'])
def delete_mapping(mapping_id):
    mapping = CustomUnitMapping.query.get_or_404(mapping_id)
    try:
        db.session.delete(mapping)
        db.session.commit()
        flash('Mapping deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting mapping: {str(e)}', 'error')
        return redirect(url_for('conversion.manage_mappings'))

    # Get all units and mappings
    units = Unit.query.all()
    mappings = CustomUnitMapping.query.all()
    return render_template("conversion/mappings.html", units=units, mappings=mappings)

@conversion_bp.route('/logs')
def view_logs():
    logs = ConversionLog.query.order_by(ConversionLog.timestamp.desc()).all()
    return render_template('conversion/logs.html', logs=logs)