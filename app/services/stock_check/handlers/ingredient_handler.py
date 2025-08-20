
"""
Ingredient-specific stock checking handler
"""

import logging
from typing import Optional

from app.models import InventoryItem
from app.services.unit_conversion import ConversionEngine
# Import moved to avoid circular dependency - use direct model access
# from ...blueprints.fifo.services import FIFOService
from ..types import StockCheckRequest, StockCheckResult, StockStatus, InventoryCategory
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


class IngredientHandler(BaseInventoryHandler):
    """Handler for ingredient stock checking with FIFO support"""
    
    def check_availability(self, request: StockCheckRequest) -> StockCheckResult:
        """
        Check ingredient availability using FIFO entries.
        
        Args:
            request: Stock check request
            
        Returns:
            Stock check result
        """
        ingredient = InventoryItem.query.get(request.item_id)
        if not ingredient:
            return self._create_not_found_result(request)
            
        if not self._check_organization_access(ingredient):
            return self._create_access_denied_result(request)
        
        # Get available FIFO entries (excludes expired automatically)
        from app.models import InventoryHistory
        available_entries = InventoryHistory.query.filter_by(
            inventory_item_id=ingredient.id,
            remaining_quantity__gt=0
        ).order_by(InventoryHistory.timestamp.asc()).all()
        total_available = sum(entry.remaining_quantity for entry in available_entries)
        
        stock_unit = ingredient.unit
        recipe_unit = request.unit
        
        logger.debug(f"Ingredient {ingredient.name}: {total_available} {stock_unit} available, need {request.quantity_needed} {recipe_unit}")
        
        try:
            # Convert available stock to recipe unit
            conversion_result = ConversionEngine.convert_units(
                total_available,
                stock_unit,
                recipe_unit,
                ingredient_id=ingredient.id
            )
            
            if isinstance(conversion_result, dict):
                available_converted = conversion_result['converted_value']
                conversion_details = conversion_result
            else:
                available_converted = float(conversion_result)
                conversion_details = None
                
            status = self._determine_status(available_converted, request.quantity_needed)
            
            return StockCheckResult(
                item_id=ingredient.id,
                item_name=ingredient.name,
                category=InventoryCategory.INGREDIENT,
                needed_quantity=request.quantity_needed,
                needed_unit=recipe_unit,
                available_quantity=available_converted,
                available_unit=recipe_unit,
                raw_stock=total_available,
                stock_unit=stock_unit,
                status=status,
                formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                formatted_available=self._format_quantity_display(available_converted, recipe_unit),
                conversion_details=conversion_details
            )
            
        except ValueError as e:
            error_msg = str(e)
            status = StockStatus.DENSITY_MISSING if "density" in error_msg.lower() else StockStatus.ERROR
            
            return StockCheckResult(
                item_id=ingredient.id,
                item_name=ingredient.name,
                category=InventoryCategory.INGREDIENT,
                needed_quantity=request.quantity_needed,
                needed_unit=recipe_unit,
                available_quantity=0,
                available_unit=recipe_unit,
                raw_stock=total_available,
                stock_unit=stock_unit,
                status=status,
                error_message=error_msg,
                formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                formatted_available="N/A"
            )
    
    def get_item_details(self, item_id: int) -> Optional[dict]:
        """Get ingredient details"""
        ingredient = InventoryItem.query.get(item_id)
        if not ingredient or not self._check_organization_access(ingredient):
            return None
            
        return {
            'id': ingredient.id,
            'name': ingredient.name,
            'unit': ingredient.unit,
            'quantity': ingredient.quantity,
            'cost_per_unit': ingredient.cost_per_unit,
            'density': getattr(ingredient, 'density', None),
            'type': ingredient.type
        }
    
    def _create_not_found_result(self, request: StockCheckRequest) -> StockCheckResult:
        """Create result for item not found"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Unknown Ingredient',
            category=InventoryCategory.INGREDIENT,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=0,
            available_unit=request.unit,
            status=StockStatus.ERROR,
            error_message='Ingredient not found',
            formatted_needed=self._format_quantity_display(request.quantity_needed, request.unit),
            formatted_available="0"
        )
    
    def _create_access_denied_result(self, request: StockCheckRequest) -> StockCheckResult:
        """Create result for access denied"""
        return StockCheckResult(
            item_id=request.item_id,
            item_name='Access Denied',
            category=InventoryCategory.INGREDIENT,
            needed_quantity=request.quantity_needed,
            needed_unit=request.unit,
            available_quantity=0,
            available_unit=request.unit,
            status=StockStatus.ERROR,
            error_message='Access denied',
            formatted_needed=self._format_quantity_display(request.quantity_needed, request.unit),
            formatted_available="0"
        )
