
import logging
from flask_login import current_user

from app.models import db, Batch, Recipe, InventoryItem, BatchIngredient, BatchContainer
from app.models import ExtraBatchIngredient, ExtraBatchContainer, Product
from app.services.base_service import BaseService
from app.services.stock_check.core import UniversalStockCheckService
from app.services.stock_check.types import StockCheckRequest, InventoryCategory
from app.models.recipe import RecipeIngredient
from app.utils.unit_utils import get_global_unit_list

logger = logging.getLogger(__name__)

class BatchManagementService(BaseService):
    """Service for batch data management, cost calculations, and inventory integration"""
    
    @classmethod
    def get_batch_cost_summary(cls, batch):
        """Calculate comprehensive cost summary for a batch"""
        try:
            # Regular batch ingredients
            ingredient_total = sum((ing.quantity_used or 0) * (ing.cost_per_unit or 0) for ing in batch.batch_ingredients)
            
            # Regular containers
            container_total = sum((c.quantity_used or 0) * (c.cost_each or 0) for c in batch.containers)
            
            # Extra ingredients
            extras_total = sum((e.quantity_used or 0) * (e.cost_per_unit or 0) for e in batch.extra_ingredients)
            
            # Extra containers
            extra_container_total = sum((e.quantity_used or 0) * (e.cost_each or 0) for e in batch.extra_containers)
            
            total_cost = ingredient_total + container_total + extras_total + extra_container_total

            return {
                'ingredient_total': ingredient_total,
                'container_total': container_total,
                'extras_total': extras_total,
                'extra_container_total': extra_container_total,
                'total_cost': total_cost
            }

        except Exception as e:
            logger.error(f"Error calculating batch cost summary: {str(e)}")
            return {
                'ingredient_total': 0,
                'container_total': 0,
                'extras_total': 0,
                'extra_container_total': 0,
                'total_cost': 0
            }

    @classmethod
    def get_available_ingredients_for_batch(cls, recipe_id, scale=1.0):
        """Get available ingredients for a recipe using USCS"""
        try:
            recipe = Recipe.query.get(recipe_id)
            if not recipe:
                return None, "Recipe not found"

            scale = float(scale)

            # Get recipe ingredients first
            recipe_ingredients = RecipeIngredient.query.filter_by(recipe_id=recipe_id).all()

            # Create stock check requests for recipe ingredients
            stock_requests = []
            recipe_ingredient_ids = []

            for recipe_ingredient in recipe_ingredients:
                request_obj = StockCheckRequest(
                    inventory_category=InventoryCategory.INGREDIENT,
                    item_id=recipe_ingredient.ingredient_id,
                    required_amount=recipe_ingredient.amount * scale,
                    required_unit=recipe_ingredient.unit,
                    organization_id=current_user.organization_id
                )
                stock_requests.append(request_obj)
                recipe_ingredient_ids.append(recipe_ingredient.ingredient_id)

            # Use USCS to check stock
            uscs = UniversalStockCheckService()
            stock_results = uscs.check_stock(stock_requests)

            ingredients_data = []

            # Process recipe ingredients with stock check results
            for result in stock_results:
                ingredients_data.append({
                    'id': result.item_id,
                    'name': result.name,
                    'needed_amount': result.required_amount or 0,
                    'needed_unit': result.required_unit or result.unit,
                    'available_amount': result.available,
                    'inventory_unit': result.unit,
                    'status': 'sufficient' if result.status == 'AVAILABLE' else 'insufficient',
                    'category': 'recipe_ingredient'
                })

            # Get all other ingredients available to organization using USCS
            additional_request = StockCheckRequest(
                inventory_category=InventoryCategory.INGREDIENT,
                organization_id=current_user.organization_id
            )
            additional_results = uscs.check_stock([additional_request])

            # Filter out recipe ingredients we already have
            for result in additional_results:
                if result.item_id not in recipe_ingredient_ids:
                    ingredients_data.append({
                        'id': result.item_id,
                        'name': result.name,
                        'needed_amount': 0,
                        'needed_unit': result.unit,
                        'available_amount': result.available,
                        'inventory_unit': result.unit,
                        'status': 'available' if result.status == 'AVAILABLE' else 'insufficient',
                        'category': 'additional_ingredient'
                    })

            return ingredients_data, None

        except Exception as e:
            logger.error(f"Error getting available ingredients: {str(e)}")
            return None, str(e)

    @classmethod
    def get_batch_context_data(cls, batch):
        """Get all context data needed for batch in progress view"""
        try:
            # Get existing batch data
            ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
            containers = BatchContainer.query.filter_by(batch_id=batch.id).all()
            
            # Recipe data comes through the batch relationship
            recipe = batch.recipe

            # Get units for dropdown
            units = get_global_unit_list()

            # Build cost summary
            cost_summary = cls.get_batch_cost_summary(batch)

            # Get inventory items
            all_ingredients = InventoryItem.query.filter_by(type='ingredient').order_by(InventoryItem.name).all()
            inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()

            # Get products for finish batch modal
            products = Product.query.filter_by(
                is_active=True,
                organization_id=current_user.organization_id
            ).all()

            # Calculate container breakdown for finish modal
            container_breakdown = []
            if batch.containers:
                for container_usage in batch.containers:
                    container = container_usage.container
                    if container.capacity and container.capacity_unit:
                        container_breakdown.append({
                            'container': container,
                            'size_label': f"{container.capacity} {container.capacity_unit}",
                            'original_used': container_usage.quantity_used or 0
                        })

            return {
                'ingredients': ingredients,
                'containers': containers,
                'recipe': recipe,
                'units': units,
                'cost_summary': cost_summary,
                'all_ingredients': all_ingredients,
                'inventory_items': inventory_items,
                'products': products,
                'container_breakdown': container_breakdown,
                'product_quantity': getattr(batch, 'product_quantity', None)
            }

        except Exception as e:
            logger.error(f"Error getting batch context data: {str(e)}")
            raise

    @classmethod
    def get_batch_navigation_data(cls, batch):
        """Get navigation data for batch views"""
        try:
            from .core import BatchService
            
            # Find adjacent batches based on current status
            prev_batch, next_batch = BatchService.get_adjacent_batches(batch)
            
            return {
                'prev_batch': prev_batch,
                'next_batch': next_batch
            }

        except Exception as e:
            logger.error(f"Error getting batch navigation data: {str(e)}")
            return {'prev_batch': None, 'next_batch': None}

    @classmethod
    def prepare_batch_list_data(cls, filters=None, pagination_config=None):
        """Prepare all data needed for batch list view"""
        try:
            from .core import BatchService
            
            filters = filters or {}
            pagination_config = pagination_config or {
                'in_progress_page': 1,
                'completed_page': 1,
                'table_per_page': 10,
                'card_per_page': 8
            }

            # Get filtered queries
            status = filters.get('status', 'all')
            recipe_id = filters.get('recipe_id')
            start_date = filters.get('start')
            end_date = filters.get('end')
            sort_by = filters.get('sort_by', 'date_desc')

            # Get paginated batches
            in_progress_pagination = BatchService.get_paginated_batches(
                'in_progress',
                per_page=pagination_config['card_per_page'],
                page=pagination_config['in_progress_page'],
                sort_by=sort_by
            )
            
            completed_pagination = BatchService.get_paginated_batches(
                'completed',  # This will include all non-in-progress statuses
                per_page=pagination_config['table_per_page'],
                page=pagination_config['completed_page'],
                sort_by=sort_by
            )

            # Calculate costs for all batches
            all_batches = in_progress_pagination.items + completed_pagination.items
            BatchService.calculate_batch_costs(all_batches)

            # Apply cost-based sorting if needed
            if sort_by == 'cost_desc':
                in_progress_pagination.items.sort(key=lambda x: x.total_cost or 0, reverse=True)
                completed_pagination.items.sort(key=lambda x: x.total_cost or 0, reverse=True)
            elif sort_by == 'cost_asc':
                in_progress_pagination.items.sort(key=lambda x: x.total_cost or 0, reverse=False)
                completed_pagination.items.sort(key=lambda x: x.total_cost or 0, reverse=False)

            # Get all recipes for filter dropdown
            all_recipes = Recipe.query.order_by(Recipe.name).all()

            return {
                'batches': all_batches,
                'in_progress_batches': in_progress_pagination.items,
                'completed_batches': completed_pagination.items,
                'in_progress_pagination': in_progress_pagination,
                'completed_pagination': completed_pagination,
                'all_recipes': all_recipes
            }

        except Exception as e:
            logger.error(f"Error preparing batch list data: {str(e)}")
            raise
