from flask import request, jsonify, render_template, redirect, url_for
from flask_login import current_user
from ...models import db, Unit, InventoryItem, InventoryHistory
# Removed unused import - using current_user.organization_id directly
from . import quick_add_bp

# Placeholder for CSRF validation and logger if they were used in the original quick_add_ingredient
# In a real scenario, these would be imported or defined.
# For this example, we'll assume they are handled by the called functions or are not strictly needed for the refactoring.
# from itsdangerous import validate_csrf
# from app import logger

@quick_add_bp.route('/product', methods=['POST'])
def quick_add_product():
    """Quick add product - delegates to existing product creation route"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Redirect to existing product creation endpoint
        # Assuming create_product_from_data is available and handles DB operations
        from ...blueprints.products.products import create_product_from_data

        # Format data for existing product creation
        product_data = {
            'name': data['name'],
            'unit': data.get('unit', 'count'),
            'type': 'product',
            'quick_add': True  # Flag to indicate this came from quick add
        }

        result = create_product_from_data(product_data)

        if result.get('success'):
            return jsonify({
                'success': True,
                'product': result['product']
            })
        else:
            return jsonify({'error': result.get('error', 'Failed to create product')}), 500

    except Exception as e:
        # In a real scenario, log the exception
        # logger.error(f"Error in quick_add_product: {str(e)}")
        return jsonify({'error': str(e)}), 500

@quick_add_bp.route('/container', methods=['POST'])
def quick_add_container():
    """Quick add container - delegates to existing inventory creation"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        # Get form data (handles both JSON and form submissions)
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Use existing inventory creation route
        # Assuming create_inventory_item is available and handles DB operations
        from ...blueprints.inventory.routes import create_inventory_item

        # Format data for existing inventory creation
        inventory_data = {
            'name': data['name'],
            'type': 'container',
            'unit': '',  # Containers have empty unit field
            'storage_amount': float(data['storage_amount']),
            'storage_unit': data['storage_unit'],
            'quantity': 0,
            'cost_per_unit': 0, # Assuming default cost_per_unit if not provided
            'quick_add': True
        }

        result = create_inventory_item(inventory_data)

        if result.get('success'):
            container = result['item']
            return jsonify({
                'id': container.id,
                'name': container.name,
                'storage_amount': container.storage_amount,
                'storage_unit': container.storage_unit
            })
        else:
            return jsonify({'error': result.get('error', 'Failed to create container')}), 400

    except Exception as e:
        # In a real scenario, log the exception
        # logger.error(f"Error in quick_add_container: {str(e)}")
        return jsonify({'error': str(e)}), 400

@quick_add_bp.route('/unit', methods=['POST'])
def quick_add_unit():
    """Quick add unit - simplified unit creation"""
    try:
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401

        # Get organization context
        if hasattr(current_user, 'organization_id') and current_user.organization_id:
            organization_id = current_user.organization_id
        elif current_user.user_type == 'developer':
            organization_id = None  # Developer users can create global units
        else:
            return jsonify({"error": "No organization context"}), 403

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

        # Create new unit (this is simple enough to keep here)
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
        # In a real scenario, log the exception
        # logger.error(f"Error creating unit: {str(e)}")
        return jsonify({'error': str(e)}), 500

@quick_add_bp.route('/ingredient', methods=['GET', 'POST'])
def quick_add_ingredient():
    """Quick add ingredient - delegates to existing inventory creation"""
    if request.method == 'GET':
        # Return the modal with units
        # Ensure is_active is checked as in original code
        units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
        return render_template('components/modals/quick_add_ingredient_modal.html', units=units)

    try:
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        name = data.get('name')
        unit = data.get('unit')

        if not name or not unit:
            return jsonify({"error": "Missing name or unit"}), 400

        # Use existing inventory creation route
        # Assuming create_inventory_item is available and handles DB operations
        from ...blueprints.inventory.routes import create_inventory_item

        # Check if unit requires density (volume units)
        from_unit = Unit.query.filter_by(name=unit, is_active=True).first() # Added is_active check for unit
        density = 1.0 if from_unit and from_unit.unit_type in ['volume'] else None

        inventory_data = {
            'name': name,
            'type': 'ingredient',
            'unit': unit,
            'quantity': 0.0,
            'cost_per_unit': 0.0,
            'density': density,
            'quick_add': True
        }

        result = create_inventory_item(inventory_data)

        if result.get('success'):
            item = result['item']
            message = "Added with default water density (1.0 g/mL). Update if needed." if density else "Added successfully."

            return jsonify({
                "id": item.id,
                "name": item.name,
                "unit": item.unit,
                "message": message
            }), 200
        else:
            return jsonify({"error": result.get('error', 'Failed to create ingredient')}), 500

    except Exception as e:
        # In a real scenario, log the exception
        # logger.error(f"Error in quick_add_ingredient: {str(e)}")
        return jsonify({"error": str(e)}), 500