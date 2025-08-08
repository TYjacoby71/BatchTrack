from flask import request, jsonify, render_template, redirect, url_for, current_app
from flask_login import current_user
from ...models import db, Unit, InventoryItem, InventoryHistory
from . import quick_add_bp
import traceback

def get_user_organization_id():
    """Helper function to get organization context with debugging"""
    try:
        current_app.logger.info(f"Quick Add: Getting organization context for user {current_user.id if current_user.is_authenticated else 'anonymous'}")

        if not current_user.is_authenticated:
            current_app.logger.warning("Quick Add: User not authenticated")
            return None, "Authentication required"

        current_app.logger.info(f"Quick Add: User type: {current_user.user_type}")
        current_app.logger.info(f"Quick Add: User organization_id: {getattr(current_user, 'organization_id', 'NOT_SET')}")

        if hasattr(current_user, 'organization_id') and current_user.organization_id:
            organization_id = current_user.organization_id
            current_app.logger.info(f"Quick Add: Using organization_id: {organization_id}")
            return organization_id, None
        elif current_user.user_type == 'developer':
            current_app.logger.info("Quick Add: Developer user - allowing global access")
            return None, None  # Developer users can create global items
        else:
            current_app.logger.error("Quick Add: No organization context found")
            return None, "No organization context"
    except Exception as e:
        current_app.logger.error(f"Quick Add: Error getting organization context: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return None, f"Error getting organization context: {str(e)}"

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
        current_app.logger.info("Quick Add Container: POST request started")

        organization_id, error = get_user_organization_id()
        if error:
            current_app.logger.error(f"Quick Add Container: {error}")
            return jsonify({"error": error}), 401 if "Authentication" in error else 403

        # Get form data (handles both JSON and form submissions)
        if request.is_json:
            data = request.get_json()
            current_app.logger.info("Quick Add Container: Processing JSON data")
        else:
            data = request.form.to_dict()
            current_app.logger.info("Quick Add Container: Processing form data")

        if not data:
            current_app.logger.error("Quick Add Container: No data provided")
            return jsonify({'error': 'No data provided'}), 400

        current_app.logger.info(f"Quick Add Container: Received data: {data}")

        # Use existing inventory creation route
        from ...blueprints.inventory.routes import create_inventory_item

        # Format data for existing inventory creation
        inventory_data = {
            'name': data['name'],
            'type': 'container',
            'unit': '',  # Containers have empty unit field
            'storage_amount': float(data['storage_amount']),
            'storage_unit': data['storage_unit'],
            'quantity': 0,
            'cost_per_unit': 0,
            'organization_id': organization_id,
            'quick_add': True
        }

        current_app.logger.info(f"Quick Add Container: Calling create_inventory_item with data: {inventory_data}")
        result = create_inventory_item(inventory_data)
        current_app.logger.info(f"Quick Add Container: create_inventory_item result: {result}")

        if result.get('success'):
            container = result['item']
            response_data = {
                'id': container.id,
                'name': container.name,
                'storage_amount': container.storage_amount,
                'storage_unit': container.storage_unit
            }
            current_app.logger.info(f"Quick Add Container: Success response: {response_data}")
            return jsonify(response_data)
        else:
            error_msg = result.get('error', 'Failed to create container')
            current_app.logger.error(f"Quick Add Container: create_inventory_item failed: {error_msg}")
            return jsonify({'error': error_msg}), 400

    except Exception as e:
        current_app.logger.error(f"Quick Add Container: Exception occurred: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 400

@quick_add_bp.route('/unit', methods=['POST'])
def quick_add_unit():
    """Quick add unit - simplified unit creation"""
    try:
        current_app.logger.info("Quick Add Unit: POST request started")

        organization_id, error = get_user_organization_id()
        if error:
            current_app.logger.error(f"Quick Add Unit: {error}")
            return jsonify({"error": error}), 401 if "Authentication" in error else 403

        data = request.get_json()
        if not data:
            current_app.logger.error("Quick Add Unit: No data provided")
            return jsonify({'error': 'No data provided'}), 400

        current_app.logger.info(f"Quick Add Unit: Received data: {data}")

        name = data.get('name', '').strip()
        unit_type = data.get('type', 'weight')

        if not name:
            current_app.logger.error("Quick Add Unit: Unit name is required")
            return jsonify({'error': 'Unit name is required'}), 400

        current_app.logger.info(f"Quick Add Unit: Creating unit '{name}' of type '{unit_type}'")

        # Check if unit already exists in organization scope
        existing_unit = Unit.query.filter_by(name=name, organization_id=organization_id).first()
        if existing_unit:
            current_app.logger.warning(f"Quick Add Unit: Unit '{name}' already exists")
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

        current_app.logger.info(f"Quick Add Unit: Adding unit to database: {new_unit.name}")
        db.session.add(new_unit)
        db.session.commit()

        response_data = {
            'name': new_unit.name,
            'id': new_unit.id,
            'symbol': new_unit.symbol,
            'type': new_unit.unit_type
        }
        current_app.logger.info(f"Quick Add Unit: Success response: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Quick Add Unit: Exception occurred: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@quick_add_bp.route('/ingredient', methods=['GET', 'POST'])
def quick_add_ingredient():
    """Quick add ingredient - delegates to existing inventory creation"""
    if request.method == 'GET':
        try:
            current_app.logger.info("Quick Add Ingredient: GET request for modal")
            # Return the modal with units
            units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
            current_app.logger.info(f"Quick Add Ingredient: Found {len(units)} active units")
            return render_template('components/modals/quick_add_ingredient_modal.html', units=units)
        except Exception as e:
            current_app.logger.error(f"Quick Add Ingredient GET error: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    try:
        current_app.logger.info("Quick Add Ingredient: POST request started")

        organization_id, error = get_user_organization_id()
        if error:
            current_app.logger.error(f"Quick Add Ingredient: {error}")
            return jsonify({"error": error}), 401 if "Authentication" in error else 403

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            current_app.logger.info("Quick Add Ingredient: Processing JSON data")
        else:
            data = request.form.to_dict()
            current_app.logger.info("Quick Add Ingredient: Processing form data")

        current_app.logger.info(f"Quick Add Ingredient: Received data: {data}")

        name = data.get('name')
        unit = data.get('unit')

        if not name or not unit:
            current_app.logger.error(f"Quick Add Ingredient: Missing required fields - name: {name}, unit: {unit}")
            return jsonify({"error": "Missing name or unit"}), 400

        current_app.logger.info(f"Quick Add Ingredient: Creating ingredient '{name}' with unit '{unit}'")

        # Use existing inventory creation route
        from ...blueprints.inventory.routes import create_inventory_item

        # Check if unit requires density (volume units)
        from_unit = Unit.query.filter_by(name=unit, is_active=True).first()
        density = 1.0 if from_unit and from_unit.unit_type in ['volume'] else None
        current_app.logger.info(f"Quick Add Ingredient: Unit type: {from_unit.unit_type if from_unit else 'NOT_FOUND'}, density: {density}")

        inventory_data = {
            'name': name,
            'type': 'ingredient',
            'unit': unit,
            'quantity': 0.0,
            'cost_per_unit': 0.0,
            'density': density,
            'organization_id': organization_id,
            'quick_add': True
        }

        current_app.logger.info(f"Quick Add Ingredient: Calling create_inventory_item with data: {inventory_data}")
        result = create_inventory_item(inventory_data)
        current_app.logger.info(f"Quick Add Ingredient: create_inventory_item result: {result}")

        if result.get('success'):
            item = result['item']
            message = "Added with default water density (1.0 g/mL). Update if needed." if density else "Added successfully."

            response_data = {
                "id": item.id,
                "name": item.name,
                "unit": item.unit,
                "message": message
            }
            current_app.logger.info(f"Quick Add Ingredient: Success response: {response_data}")
            return jsonify(response_data), 200
        else:
            error_msg = result.get('error', 'Failed to create ingredient')
            current_app.logger.error(f"Quick Add Ingredient: create_inventory_item failed: {error_msg}")
            return jsonify({"error": error_msg}), 500

    except Exception as e:
        current_app.logger.error(f"Quick Add Ingredient: Exception occurred: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500