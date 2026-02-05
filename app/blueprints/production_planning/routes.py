from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import production_planning_bp
from app.extensions import db
from app.models import Recipe, InventoryItem
from app.utils.permissions import require_permission

from app.services.production_planning import plan_production_comprehensive
from app.services.production_planning._container_management import analyze_container_options
from app.services.recipe_service import get_recipe_details
import logging

logger = logging.getLogger(__name__)

@production_planning_bp.route('/recipe/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.plan_production')
def plan_production_route(recipe_id):
    """Production planning route - delegates to service"""
    recipe = get_recipe_details(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))
    if recipe.is_archived:
        flash('Archived recipes cannot be planned for production.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()

            scale = float(data.get('scale', 1.0))
            container_id = data.get('container_id')

            # Delegate to service - no business logic here
            planning_result = plan_production_comprehensive(recipe_id, scale, container_id)

            if planning_result.get('success', False):
                return jsonify({
                    'success': True,
                    'stock_results': planning_result.get('stock_results', []),
                    'all_available': planning_result.get('all_available', False),
                    'scale': scale,
                    'cost_info': planning_result.get('cost_info', {}),
                    'all_ok': planning_result.get('all_available', False)  # For backwards compatibility
                })
            else:
                error_msg = planning_result.get('error') or planning_result.get('message') or 'Production planning failed'
                return jsonify({'success': False, 'error': error_msg}), 500

        except Exception as e:
            logger.error(f"Error in production planning: {str(e)}")
            return jsonify({'success': False, 'error': 'Production planning failed'}), 500

    # GET request - show planning form
    return render_template('pages/production_planning/plan_production.html', recipe=recipe, breadcrumb_items=[
        {'label': 'Dashboard', 'url': url_for('app_routes.dashboard')},
        {'label': 'Recipes', 'url': url_for('recipes.list_recipes')},
        {'label': recipe.name, 'url': url_for('recipes.view_recipe', recipe_id=recipe.id)},
        {'label': 'Plan Production'}
    ])

@production_planning_bp.route('/recipe/<int:recipe_id>/auto-fill-containers', methods=['POST'])
@login_required
@require_permission('recipes.plan_production')
def auto_fill_containers(recipe_id):
    """Auto-fill containers for recipe production planning"""
    try:
        data = request.get_json()
        scale = data.get('scale', 1.0)

        recipe = Recipe.query.get_or_404(recipe_id)
        if recipe.is_archived:
            return jsonify({'success': False, 'error': 'Archived recipes cannot be planned for production.'}), 400

        # Use the simplified container management
        # Allow optional product_density to be passed for cross-type conversions
        product_density = data.get('product_density')
        try:
            product_density = float(product_density) if product_density is not None else None
        except (TypeError, ValueError):
            product_density = None

        strategy, container_options = analyze_container_options(
            recipe=recipe,
            scale=scale,
            organization_id=current_user.organization_id,
            api_format=True,
            product_density=product_density,
            fill_pct=data.get('fill_pct')
        )

        if strategy:
            # Include container_options and yield metadata for FE manual mode
            strategy['container_options'] = container_options
            strategy['yield_amount'] = (recipe.predicted_yield or 0) * float(scale)
            strategy['yield_unit'] = recipe.predicted_yield_unit or 'units'
            return jsonify(strategy)
        else:
            return jsonify({
                'success': False,
                'error': 'No suitable container strategy found',
                'container_options': container_options
            }), 400

    except Exception as e:
        logger.error(f"Error in auto-fill containers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@production_planning_bp.route('/recipe/<int:recipe_id>/debug/containers')
@login_required
@require_permission('recipes.plan_production')
def debug_recipe_containers(recipe_id):
    """Debug endpoint to check available containers for recipe"""
    try:
        from app.models import Recipe, InventoryItem, IngredientCategory

        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Check for allowed containers
        allowed = []
        if hasattr(recipe, 'allowed_containers'):
            allowed = [str(c) for c in recipe.allowed_containers] if recipe.allowed_containers else []

        # Get all available containers in org
        container_category = IngredientCategory.query.filter_by(
            name='Container',
            organization_id=current_user.organization_id
        ).first()

        all_containers = []
        if container_category:
            containers = InventoryItem.query.filter_by(
                organization_id=current_user.organization_id,
                category_id=container_category.id
            ).all()
            all_containers = [{'id': c.id, 'name': c.container_display_name, 'capacity': getattr(c, 'capacity', 0)} for c in containers]

        return jsonify({
            'recipe_id': recipe_id,
            'recipe_name': recipe.name,
            'allowed_containers': allowed,
            'all_containers': all_containers,
            'container_category_found': container_category is not None
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@production_planning_bp.route('/recipe/<int:recipe_id>/plan/container', methods=['POST'])
@login_required
@require_permission('recipes.plan_production')
def plan_container_route(recipe_id):
    """API route to get container plan for a recipe"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        scale = float(data.get('scale', 1.0))
        yield_amount = float(data.get('yield_amount'))
        yield_unit = data.get('yield_unit')
        preferred_container_id = data.get('preferred_container_id')
        fill_pct = data.get('fill_pct')

        if not scale or not yield_amount or not yield_unit:
            return jsonify({"error": "Scale, yield amount, and yield unit are required"}), 400

        # Delegate to service
        # Import production_service dynamically to avoid circular imports
        from app.services.production_planning import ProductionPlanningService
        production_service = ProductionPlanningService()

        container_result = production_service.analyze_containers(
            recipe=recipe,
            scale=scale,
            preferred_container_id=preferred_container_id,
            fill_pct=fill_pct
        )

        # If container analysis returns a drawer payload, return it immediately
        if isinstance(container_result, dict) and container_result.get('drawer_payload'):
            return jsonify(container_result)


        return jsonify(container_result)

    except Exception as e:
        logger.error(f"Error in container planning API: {e}")
        return jsonify({"error": str(e)}), 500

@production_planning_bp.route('/stock/check', methods=['POST'])
@login_required
@require_permission('inventory.view')
def check_stock():
    """Check stock for a recipe using the recipe service (internally uses USCS)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))

        if not recipe_id:
            return jsonify({"error": "Recipe ID is required"}), 400

        # Get recipe
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        # Use USCS directly
        from app.services.stock_check.core import UniversalStockCheckService
        uscs = UniversalStockCheckService()

        result = uscs.check_recipe_stock(recipe_id, scale)

        # Process results for frontend
        if result.get('success'):
            stock_check = result.get('stock_check', [])
            # Convert USCS status values to frontend expected values
            for item in stock_check:
                if item.get('status') == 'needed':
                    item['status'] = 'NEEDED'
                elif item.get('status') == 'low':
                    item['status'] = 'LOW'
                elif item.get('status') == 'good':
                    item['status'] = 'OK'

                # Ensure frontend expected fields exist
                item['ingredient_name'] = item.get('item_name', item.get('ingredient_name', 'Unknown'))
                item['needed_amount'] = item.get('needed_quantity', 0)
                item['available_quantity'] = item.get('available_quantity', 0)
                item['unit'] = item.get('needed_unit', item.get('unit', ''))

            all_ok = all(item.get('status') not in ['NEEDED', 'INSUFFICIENT'] for item in stock_check)
            status = 'ok' if all_ok else 'insufficient'
        else:
            stock_check = result.get('stock_check', [])  # Include stock check data even on error
            all_ok = False
            status = 'error'

        return jsonify({
            "stock_check": stock_check,
            "status": status,
            "all_ok": all_ok,
            "recipe_name": recipe.name,
            "success": result.get('success', False),
            "error": result.get('error'),
            # Bubble any drawer instructions to the frontend for DrawerProtocol
            "drawer_payload": result.get('drawer_payload')
        }), 200
    except Exception as e:
        logger.error(f"Error in recipe stock check: {e}")
        return jsonify({"error": str(e)}), 500