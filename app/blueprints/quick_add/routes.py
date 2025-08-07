from flask import request, jsonify, render_template
from ...models import db, InventoryItem, Unit
from . import quick_add_bp

@quick_add_bp.route('/product', methods=['POST'])
def quick_add_product():
    try:
        from flask_login import current_user
        from ...models import InventoryHistory
        from ...utils.permissions import get_effective_organization_id

        # Ensure user is authenticated and get organization context
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        organization_id = get_effective_organization_id()
        if not organization_id and current_user.user_type != 'developer':
            return jsonify({'error': 'No organization context'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        product = InventoryItem(
            name=data['name'],
            type='product',
            unit=data.get('unit', 'count'),
            quantity=0,
            organization_id=organization_id
        )

        db.session.add(product)
        db.session.flush()  # Get the ID without committing

        # Create initial history entry for FIFO tracking
        history = InventoryHistory(
            inventory_item_id=product.id,
            change_type='restock',
            quantity_change=0,
            remaining_quantity=0,
            unit=product.unit,
            unit_cost=0,
            note='Initial product creation via quick add',
            created_by=current_user.id if current_user else None,
            quantity_used=0,
            is_perishable=False,
            organization_id=organization_id
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'unit': product.unit
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@quick_add_bp.route('/container', methods=['POST'])
def quick_add_container():
    try:
        from flask_login import current_user
        from ...models import InventoryHistory
        from ...utils.permissions import get_effective_organization_id

        # Ensure user is authenticated and get organization context
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        organization_id = get_effective_organization_id()
        if not organization_id and current_user.user_type != 'developer':
            return jsonify({'error': 'No organization context'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        container = InventoryItem(
            name=data['name'],
            type='container',
            unit='',  # Containers have empty unit field
            storage_amount=float(data['storage_amount']),
            storage_unit=data['storage_unit'],
            quantity=0,
            organization_id=organization_id
        )

        db.session.add(container)
        db.session.flush()  # Get the ID without committing

        # Create initial history entry for FIFO tracking (0 quantity to prime the system)
        history = InventoryHistory(
            inventory_item_id=container.id,
            change_type='restock',
            quantity_change=0,
            remaining_quantity=0,  # For FIFO tracking
            unit='count',  # Containers are always counted
            unit_cost=0,
            note='Initial container creation via quick add',
            created_by=current_user.id if current_user else None,
            quantity_used=0,  # Required field for FIFO tracking
            is_perishable=False,
            organization_id=organization_id
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            'id': container.id,
            'name': container.name,
            'storage_amount': container.storage_amount,
            'storage_unit': container.storage_unit
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@quick_add_bp.route('/unit', methods=['POST'])
def quick_add_unit():
    from flask_login import current_user
    from ...utils.permissions import get_effective_organization_id

    # Ensure user is authenticated and get organization context
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    organization_id = get_effective_organization_id()
    if not organization_id and current_user.user_type != 'developer':
        return jsonify({"error": "No organization context"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = data.get('name', '').strip()
        unit_type = data.get('type', 'weight')

        if not name:
            return jsonify({'error': 'Unit name is required'}), 400

        # Check if unit already exists in organization scope
        existing_unit = Unit.query.filter_by(name=name, organization_id=organization_id).first()
        if existing_unit:
            return jsonify({'error': f'Unit "{name}" already exists'}), 400

        # Create new unit
        new_unit = Unit(
            name=name,
            symbol=name.lower()[:3] if len(name) >= 3 else name.lower(),  # Simple symbol generation
            unit_type=unit_type,
            is_custom=True,  # Mark as custom unit
            organization_id=organization_id,
            created_by=current_user.id
        )

        db.session.add(new_unit)
        db.session.commit()

        return jsonify({
            'name': new_unit.name,
            'id': new_unit.id,
            'symbol': new_unit.symbol,
            'type': new_unit.unit_type
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error creating unit: {str(e)}")  # Debug logging
        return jsonify({'error': str(e)}), 500

@quick_add_bp.route('/ingredient', methods=['GET', 'POST'])
def quick_add_ingredient():
    from flask_login import current_user
    from ...utils.permissions import get_effective_organization_id
    from ...models import InventoryHistory

    # Ensure user is authenticated and get organization context
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    organization_id = get_effective_organization_id()
    if not organization_id and current_user.user_type != 'developer':
        return jsonify({"error": "No organization context"}), 403

    # If GET request, return the modal with units  
    if request.method == 'GET':
        units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
        return render_template('components/modals/quick_add_ingredient_modal.html', units=units)

    try:
        # Validate CSRF token
        try:
            validate_csrf(request.headers.get('X-CSRFToken'))
        except Exception as e:
            logger.error(f"CSRF validation failed: {str(e)}")
            return jsonify({"error": "CSRF token validation failed"}), 400

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            name = data.get('name')
            unit = data.get('unit')
        else:
            name = request.form.get('name')
            unit = request.form.get('unit')

        if not name or not unit:
            return jsonify({"error": "Missing name or unit"}), 400

        # Check for existing within organization scope
        query = InventoryItem.query.filter_by(name=name, type='ingredient')
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        existing = query.first()

        if existing:
            return jsonify({"id": existing.id, "name": existing.name, "unit": existing.unit}), 200

        # Check if unit requires density
        from_unit = Unit.query.filter_by(name=unit).first()
        if from_unit and from_unit.unit_type in ['volume']:
            # Set default water density for volume ingredients
            new_item = InventoryItem(
                name=name,
                type='ingredient',
                unit=unit,
                quantity=0.0,
                cost_per_unit=0.0,
                density=1.0,  # Default water density
                organization_id=organization_id
            )
            message = "Added with default water density (1.0 g/mL). Update if needed."
        else:
            new_item = InventoryItem(
                name=name,
                type='ingredient',
                unit=unit,
                quantity=0.0,
                cost_per_unit=0.0,
                organization_id=organization_id
            )
            message = "Added successfully."

        db.session.add(new_item)
        db.session.flush()  # Get the ID without committing

        # Create initial history entry for FIFO tracking (0 quantity to prime the system)
        history = InventoryHistory(
            inventory_item_id=new_item.id,
            change_type='restock',
            quantity_change=0,
            remaining_quantity=0,
            unit=new_item.unit,
            unit_cost=0,
            note='Initial ingredient creation via quick add',
            created_by=current_user.id if current_user else None,
            quantity_used=0,
            is_perishable=False,
            organization_id=organization_id
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            "id": new_item.id,
            "name": new_item.name,
            "unit": new_item.unit,
            "message": message
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500