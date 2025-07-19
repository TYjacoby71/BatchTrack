from flask import request, render_template, redirect, flash, url_for, jsonify
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from ...models import db, Unit, CustomUnitMapping, InventoryItem
from flask_login import current_user
from ...services.unit_conversion import ConversionEngine
import logging
from . import conversion_bp

logger = logging.getLogger(__name__)

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
        return redirect(url_for('conversion_bp.manage_units'))

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

    return redirect(url_for('conversion_bp.manage_units'))

@conversion_bp.route('/units', methods=['GET', 'POST'])
def manage_units():
    from ...utils.unit_utils import get_global_unit_list
    from flask_wtf.csrf import validate_csrf
    from wtforms.validators import ValidationError

    if request.method == 'POST':
        try:
            csrf_token = request.form.get("csrf_token")
            validate_csrf(csrf_token)

            # Handle unit creation
            if 'unit_name' in request.form:
                name = request.form.get('unit_name').strip()
                symbol = request.form.get('unit_symbol', '').strip() or name
                unit_type = request.form.get('unit_type')

                if not name or not unit_type:
                    flash('Unit name and type are required', 'error')
                    return redirect(url_for('conversion_bp.manage_units'))

                existing = Unit.query.filter_by(name=name).first()
                if existing:
                    flash('Unit already exists', 'error')
                    return redirect(url_for('conversion_bp.manage_units'))

                # Set base unit and multiplier based on type
                base_units = {
                    'weight': 'gram',
                    'volume': 'ml',
                    'count': 'count',
                    'length': 'cm',
                    'area': 'sqcm'
                }

                new_unit = Unit(
                    name=name,
                    symbol=symbol,
                    type=unit_type,
                    base_unit=base_units.get(unit_type, 'count'),
                    conversion_factor=1.0,
                    is_custom=True,
                    is_mapped=False,  # Start as unmapped
                    created_by=current_user.id if current_user.is_authenticated else None,
                    organization_id=current_user.organization_id if current_user.is_authenticated else None
                )
                db.session.add(new_unit)
                db.session.commit()
                flash('Unit created successfully', 'success')
                return redirect(url_for('conversion_bp.manage_units'))

            # Handle custom unit mapping
            custom_unit = request.form.get("custom_unit", "").strip()
            comparable_unit = request.form.get("comparable_unit", "").strip()
            try:
                conversion_factor = float(request.form.get("conversion_factor", "0"))
            except:
                flash("Conversion factor must be a number.", "danger")
                return redirect(url_for('conversion_bp.manage_units'))

            if not custom_unit or not comparable_unit or conversion_factor <= 0:
                flash("All fields are required.", "danger")
                return redirect(url_for('conversion_bp.manage_units'))

            custom_unit_obj = Unit.query.filter_by(name=custom_unit).first()
            comparable_unit_obj = Unit.query.filter_by(name=comparable_unit).first()

            if not custom_unit_obj or not comparable_unit_obj:
                flash("Units not found in database.", "danger")
                return redirect(url_for('conversion_bp.manage_units'))

            if not custom_unit_obj.is_custom:
                flash("Only custom units can be mapped.", "danger")
                return redirect(url_for('conversion_bp.manage_units'))

            # Allow cross-type mapping only for specific cases
            if custom_unit_obj.type != comparable_unit_obj.type:
                # Allow volume ↔ weight with density
                if {'volume', 'weight'} <= {custom_unit_obj.type, comparable_unit_obj.type}:
                    pass  # This is allowed
                # Allow count ↔ volume/weight for custom units (user-defined relationships)
                elif custom_unit_obj.type == 'count' and comparable_unit_obj.type in ['volume', 'weight']:
                    pass  # This is allowed - user knows their apple size
                elif comparable_unit_obj.type == 'count' and custom_unit_obj.type in ['volume', 'weight']:
                    pass  # This is allowed - reverse direction
                else:
                    flash("This type of unit conversion is not supported.", "danger")
                    return redirect(url_for('conversion_bp.manage_units'))

            existing = CustomUnitMapping.query.filter_by(
                unit_name=custom_unit
            ).first()
            if existing:
                flash("This custom unit already has a mapping.", "warning")
                return redirect(url_for('conversion_bp.manage_units'))

            # Calculate the conversion factor to base unit
            # If 1 bucket = 1 gallon, and 1 gallon = 3785.41 ml, then bucket conversion_factor = 3785.41
            base_conversion_factor = conversion_factor * comparable_unit_obj.conversion_factor

            mapping = CustomUnitMapping(
                unit_name=custom_unit,
                conversion_factor=base_conversion_factor,
                base_unit=custom_unit_obj.base_unit
            )
            db.session.add(mapping)

            # Mark the custom unit as mapped and update its conversion factor
            custom_unit_obj.is_mapped = True
            custom_unit_obj.conversion_factor = base_conversion_factor
            db.session.commit()
            flash("Custom mapping added successfully.", "success")
            return redirect(url_for('conversion_bp.manage_units'))
        except ValidationError:
            flash("Invalid CSRF token", "danger")
            return redirect(url_for('conversion_bp.manage_units'))

    units = get_global_unit_list()
    mappings = CustomUnitMapping.query.all()

    units_by_type = {}
    for unit in units:
        if unit.type not in units_by_type:
            units_by_type[unit.type] = []
        units_by_type[unit.type].append(unit)

    return render_template('conversion/units.html', 
                         units=units, 
                         units_by_type=units_by_type, 
                         mappings=mappings)


@conversion_bp.route('/mappings/<int:mapping_id>/delete', methods=['POST'])
def delete_mapping(mapping_id):
    mapping = CustomUnitMapping.query.get_or_404(mapping_id)
    try:
        db.session.delete(mapping)
        db.session.commit()
        flash('Mapping deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting mapping: {str(e)}', 'error')
    return redirect(url_for('conversion_bp.manage_units'))

@conversion_bp.route('/validate_mapping', methods=['POST'])
def validate_mapping():
    data = request.get_json()
    from_unit = Unit.query.filter_by(name=data['from_unit']).first()
    to_unit = Unit.query.filter_by(name=data['to_unit']).first()

    if from_unit.type == to_unit.type:
        return jsonify({"valid": True})

    # Handle volume ↔ weight conversions
    if {'volume', 'weight'} <= {from_unit.type, to_unit.type}:
        if data.get('ingredient_id'):
            ingredient = InventoryItem.query.get(data['ingredient_id'])
            if not ingredient.density and not ingredient.category:
                return jsonify({
                    "valid": False,
                    "error": "Density required for volume ↔ weight conversion. Set ingredient density first."
                })
        else:
            return jsonify({
                "valid": False,
                "error": "Volume ↔ weight mappings require ingredient context"
            })

    return jsonify({"valid": True})

@conversion_bp.route('/add_mapping', methods=['POST'])
def add_mapping():
    data = request.get_json()

    # Validate units exist
    from_unit = Unit.query.filter_by(name=data['from_unit']).first()
    to_unit = Unit.query.filter_by(name=data['to_unit']).first()

    if not from_unit or not to_unit:
        return jsonify({"error": "Invalid units"}), 400

    # Cross-type validation
    if from_unit.type != to_unit.type:
        if {'volume', 'weight'} <= {from_unit.type, to_unit.type}:
            if not data.get('density'):
                return jsonify({
                    "error": "Density required for volume ↔ weight conversion"
                }), 400

    mapping = CustomUnitMapping(
        from_unit=data['from_unit'],
        to_unit=data['to_unit'],
        multiplier=float(data['multiplier'])
    )

    db.session.add(mapping)
    db.session.commit()

    return jsonify({"message": "Mapping added successfully"})