from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from app.models import db, InventoryItem, CustomUnitMapping, Unit, IngredientCategory, Recipe, Batch, Product
from app.services.unit_conversion.drawer_errors import prepare_density_error_context, prepare_unit_mapping_error_context
from app.services.unit_conversion import ConversionEngine
from app.utils.permissions import require_permission

drawer_actions_bp = Blueprint('drawer_actions', __name__, url_prefix='/api/drawer-actions')

# ==================== CONVERSION ERRORS ====================

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['GET'])
@login_required
@require_permission('view_inventory')
def density_modal(ingredient_id):
    """Get density fix modal for ingredient"""
    ingredient = InventoryItem.query.get_or_404(ingredient_id)

    try:
        modal_html = render_template('components/shared/density_fix_modal.html',
                                   ingredient=ingredient)

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def update_density(ingredient_id):
    """Update ingredient density from modal"""
    ingredient = InventoryItem.query.get_or_404(ingredient_id)

    try:
        data = request.get_json()
        new_density = float(data.get('density', 0))

        if new_density <= 0:
            return jsonify({'error': 'Density must be greater than 0'}), 400

        ingredient.density = new_density
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Density updated to {new_density} g/ml',
            'new_density': new_density
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update density: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/unit-mapping-modal', methods=['GET'])
@login_required
@require_permission('view_inventory')
def unit_mapping_modal():
    """Get unit mapping creation modal"""
    from_unit = request.args.get('from_unit', '')
    to_unit = request.args.get('to_unit', '')

    try:
        modal_html = render_template('components/shared/unit_mapping_fix_modal.html',
                                   from_unit=from_unit,
                                   to_unit=to_unit)

        return jsonify({
            'success': True,
            'modal_html': modal_html
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load modal: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/unit-mapping-modal', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def create_unit_mapping():
    """Create custom unit mapping from modal"""
    try:
        data = request.get_json()
        from_unit = data.get('from_unit', '').strip()
        to_unit = data.get('to_unit', '').strip()
        conversion_factor = float(data.get('conversion_factor', 0))

        if not from_unit or not to_unit:
            return jsonify({'error': 'Both units are required'}), 400

        if conversion_factor <= 0:
            return jsonify({'error': 'Conversion factor must be greater than 0'}), 400

        # Check if mapping already exists
        existing = CustomUnitMapping.query.filter_by(
            from_unit=from_unit,
            to_unit=to_unit,
            organization_id=current_user.organization_id
        ).first()

        if existing:
            return jsonify({'error': 'Mapping already exists'}), 400

        # Create new mapping
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            conversion_factor=conversion_factor,
            organization_id=current_user.organization_id
        )

        db.session.add(mapping)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Unit mapping created: {from_unit} → {to_unit}',
            'mapping': {
                'from_unit': from_unit,
                'to_unit': to_unit,
                'conversion_factor': conversion_factor
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create mapping: {str(e)}'}), 500
def get_density_modal(ingredient_id):
    """Get density modal for missing density error"""
    ingredient = InventoryItem.query.get_or_404(ingredient_id)

    if ingredient.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403

    suggested_density = None
    if ingredient.category and ingredient.category.default_density:
        suggested_density = ingredient.category.default_density

    modal_html = render_template('components/shared/density_fix_modal.html',
                               ingredient=ingredient,
                               suggested_density=suggested_density)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'ingredient_id': ingredient_id,
        'ingredient_name': ingredient.name,
        'current_density': ingredient.density,
        'suggested_density': suggested_density
    })

@drawer_actions_bp.route('/conversion/density-modal/<int:ingredient_id>', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def update_density(ingredient_id):
    """Update ingredient density from modal"""
    ingredient = InventoryItem.query.get_or_404(ingredient_id)

    if ingredient.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        new_density = float(data.get('density', 0))

        if new_density <= 0:
            return jsonify({'error': 'Density must be greater than 0'}), 400

        ingredient.density = new_density
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Density updated for {ingredient.name}',
            'new_density': new_density
        })

    except ValueError:
        return jsonify({'error': 'Invalid density value'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update density: {str(e)}'}), 500

@drawer_actions_bp.route('/conversion/unit-mapping-modal', methods=['GET'])
@login_required
@require_permission('view_conversion')
def get_unit_mapping_modal():
    """Get unit mapping modal for missing custom mapping error"""
    from_unit = request.args.get('from_unit')
    to_unit = request.args.get('to_unit')

    units = Unit.query.filter_by(is_active=True).order_by(Unit.name).all()

    modal_html = render_template('components/shared/unit_mapping_fix_modal.html',
                               from_unit=from_unit,
                               to_unit=to_unit,
                               units=units)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'from_unit': from_unit,
        'to_unit': to_unit
    })

@drawer_actions_bp.route('/conversion/create-unit-mapping', methods=['POST'])
@login_required
@require_permission('edit_conversion')
def create_unit_mapping():
    """Create custom unit mapping from modal"""
    try:
        data = request.get_json()
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')
        conversion_factor = float(data.get('conversion_factor', 1))

        if conversion_factor <= 0:
            return jsonify({'error': 'Conversion factor must be greater than 0'}), 400

        existing = CustomUnitMapping.query.filter_by(
            from_unit=from_unit,
            to_unit=to_unit,
            organization_id=current_user.organization_id
        ).first()

        if existing:
            return jsonify({'error': 'Mapping already exists'}), 400

        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            conversion_factor=conversion_factor,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )

        db.session.add(mapping)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Custom mapping created: 1 {from_unit} = {conversion_factor} {to_unit}'
        })

    except ValueError:
        return jsonify({'error': 'Invalid conversion factor'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create mapping: {str(e)}'}), 500

# ==================== RECIPE ERRORS ====================

@drawer_actions_bp.route('/recipe/missing-ingredient-modal/<int:recipe_id>', methods=['GET'])
@login_required
@require_permission('view_recipes')
def get_missing_ingredient_modal(recipe_id):
    """Handle missing ingredient error during recipe validation"""
    recipe = Recipe.query.get_or_404(recipe_id)

    if recipe.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403

    # Get suggested ingredients from inventory
    available_ingredients = InventoryItem.query.filter_by(
        organization_id=current_user.organization_id,
        category='ingredient'
    ).order_by(InventoryItem.name).all()

    modal_html = render_template('components/shared/missing_ingredient_fix_modal.html',
                               recipe=recipe,
                               available_ingredients=available_ingredients)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'recipe_id': recipe_id
    })

@drawer_actions_bp.route('/recipe/add-ingredient/<int:recipe_id>', methods=['POST'])
@login_required
@require_permission('edit_recipes')
def add_recipe_ingredient(recipe_id):
    """Add ingredient to recipe from modal"""
    recipe = Recipe.query.get_or_404(recipe_id)

    if recipe.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        ingredient_id = int(data.get('ingredient_id'))
        quantity = float(data.get('quantity', 1))
        unit = data.get('unit', 'gram')

        # Add ingredient to recipe using your recipe service
        from app.services.recipe_service import RecipeService
        result = RecipeService.add_ingredient_to_recipe(
            recipe_id=recipe_id,
            ingredient_id=ingredient_id,
            quantity=quantity,
            unit=unit
        )

        return jsonify({
            'success': True,
            'message': f'Ingredient added to {recipe.name}',
            'ingredient_added': result
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add ingredient: {str(e)}'}), 500

@drawer_actions_bp.route('/recipe/scaling-validation-modal/<int:recipe_id>', methods=['GET'])
@login_required
@require_permission('view_recipes')
def get_recipe_scaling_modal(recipe_id):
    """Handle recipe scaling validation errors"""
    recipe = Recipe.query.get_or_404(recipe_id)
    scale = request.args.get('scale', 1.0)
    error_details = request.args.get('error_details', '')

    modal_html = render_template('components/shared/recipe_scaling_fix_modal.html',
                               recipe=recipe,
                               scale=scale,
                               error_details=error_details)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'recipe_id': recipe_id
    })

# ==================== BATCH ERRORS ====================

@drawer_actions_bp.route('/batch/container-shortage-modal/<int:batch_id>', methods=['GET'])
@login_required
@require_permission('view_batches')
def get_container_shortage_modal(batch_id):
    """Handle container shortage during batch planning"""
    batch = Batch.query.get_or_404(batch_id)

    if batch.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403

    # Get available containers
    available_containers = InventoryItem.query.filter_by(
        organization_id=current_user.organization_id,
        category='container'
    ).filter(InventoryItem.quantity > 0).all()

    modal_html = render_template('components/shared/container_shortage_fix_modal.html',
                               batch=batch,
                               available_containers=available_containers)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'batch_id': batch_id
    })

@drawer_actions_bp.route('/batch/update-container-allocation/<int:batch_id>', methods=['POST'])
@login_required
@require_permission('edit_batches')
def update_batch_containers(batch_id):
    """Update batch container allocation from modal"""
    batch = Batch.query.get_or_404(batch_id)

    if batch.organization_id != current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        container_selections = data.get('containers', [])

        # Update batch containers using your batch service
        from app.services.batch_service import BatchService
        result = BatchService.update_container_allocation(
            batch_id=batch_id,
            container_selections=container_selections
        )

        return jsonify({
            'success': True,
            'message': f'Container allocation updated for batch {batch.batch_number}',
            'allocation': result
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update containers: {str(e)}'}), 500

@drawer_actions_bp.route('/batch/stuck-batch-modal/<int:batch_id>', methods=['GET'])
@login_required
@require_permission('view_batches')
def get_stuck_batch_modal(batch_id):
    """Handle stuck batch recovery"""
    batch = Batch.query.get_or_404(batch_id)

    modal_html = render_template('components/shared/stuck_batch_fix_modal.html',
                               batch=batch)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'batch_id': batch_id
    })

# ==================== INVENTORY ERRORS ====================

@drawer_actions_bp.route('/inventory/stock-shortage-modal/<int:item_id>', methods=['GET'])
@login_required
@require_permission('view_inventory')
def get_stock_shortage_modal(item_id):
    """Handle stock shortage during operations"""
    item = InventoryItem.query.get_or_404(item_id)
    required_amount = request.args.get('required_amount', 0)

    modal_html = render_template('components/shared/stock_shortage_fix_modal.html',
                               item=item,
                               required_amount=required_amount)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'item_id': item_id
    })

@drawer_actions_bp.route('/inventory/quick-restock/<int:item_id>', methods=['POST'])
@login_required
@require_permission('edit_inventory')
def quick_restock_item(item_id):
    """Quick restock item from modal"""
    item = InventoryItem.query.get_or_404(item_id)

    try:
        data = request.get_json()
        quantity = float(data.get('quantity', 0))
        unit_cost = float(data.get('unit_cost', 0))

        # Add inventory using your inventory service
        from app.services.inventory_adjustment import InventoryAdjustmentService
        result = InventoryAdjustmentService.add_inventory(
            item_id=item_id,
            quantity=quantity,
            unit_cost=unit_cost,
            reason='Quick restock from shortage modal'
        )

        return jsonify({
            'success': True,
            'message': f'Added {quantity} units to {item.name}',
            'new_quantity': result.get('new_quantity', 0)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to restock: {str(e)}'}), 500

# ==================== PRODUCT ERRORS ====================

@drawer_actions_bp.route('/product/sku-conflict-modal/<int:product_id>', methods=['GET'])
@login_required
@require_permission('view_products')
def get_sku_conflict_modal(product_id):
    """Handle SKU conflicts during product creation"""
    product = Product.query.get_or_404(product_id)
    conflicting_sku = request.args.get('conflicting_sku', '')

    modal_html = render_template('components/shared/sku_conflict_fix_modal.html',
                               product=product,
                               conflicting_sku=conflicting_sku)

    return jsonify({
        'success': True,
        'modal_html': modal_html,
        'product_id': product_id
    })

@drawer_actions_bp.route('/product/resolve-sku-conflict/<int:product_id>', methods=['POST'])
@login_required
@require_permission('edit_products')
def resolve_sku_conflict(product_id):
    """Resolve SKU conflict from modal"""
    product = Product.query.get_or_404(product_id)

    try:
        data = request.get_json()
        new_sku = data.get('new_sku', '')

        # Update product SKU using your product service
        from app.services.product_service import ProductService
        result = ProductService.update_sku(
            product_id=product_id,
            new_sku=new_sku
        )

        return jsonify({
            'success': True,
            'message': f'SKU updated to {new_sku}',
            'new_sku': new_sku
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update SKU: {str(e)}'}), 500

# ==================== GENERAL RETRY MECHANISM ====================

@drawer_actions_bp.route('/retry-operation', methods=['POST'])
@login_required
def retry_operation():
    """Generic retry mechanism for any fixed operation"""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        operation_data = data.get('operation_data', {})

        # Route to appropriate retry handler based on operation type
        if operation_type == 'conversion':
            return retry_conversion_operation(operation_data)
        elif operation_type == 'stock_check':
            return retry_stock_check_operation(operation_data)
        elif operation_type == 'batch_planning':
            return retry_batch_planning_operation(operation_data)
        elif operation_type == 'recipe_validation':
            return retry_recipe_validation_operation(operation_data)
        else:
            return jsonify({'error': 'Unknown operation type'}), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error_code': 'RETRY_FAILED',
            'message': f'Retry failed: {str(e)}'
        }), 500

def retry_conversion_operation(data):
    """Retry conversion after fixing underlying issue"""
    result = ConversionEngine.convert_units(
        amount=float(data.get('amount')),
        from_unit=data.get('from_unit'),
        to_unit=data.get('to_unit'),
        ingredient_id=data.get('ingredient_id')
    )
    return jsonify(result)

def retry_stock_check_operation(data):
    """Retry stock check after fixing underlying issue"""
    from app.services.stock_check import StockCheckService
    result = StockCheckService.check_recipe_stock(
        recipe_id=int(data.get('recipe_id')),
        scale=float(data.get('scale', 1.0))
    )
    return jsonify(result)

def retry_batch_planning_operation(data):
    """Retry batch planning after fixing underlying issue"""
    from app.services.production_planning import ProductionPlanningService
    result = ProductionPlanningService.create_production_plan(
        recipe_id=int(data.get('recipe_id')),
        scale=float(data.get('scale', 1.0))
    )
    return jsonify(result)

def retry_recipe_validation_operation(data):
    """Retry recipe validation after fixing underlying issue"""
    from app.services.recipe_service import RecipeService
    result = RecipeService.validate_recipe(
        recipe_id=int(data.get('recipe_id'))
    )
    return jsonify(result)