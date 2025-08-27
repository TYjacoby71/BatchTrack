"""
Ingredient-specific stock checking handler

Integrates with FIFO operations and unit conversion engine.
"""

import logging
from typing import Optional
from datetime import datetime

from app.models import InventoryItem
from app.models.inventory_lot import InventoryLot
from app.services.unit_conversion import ConversionEngine
from ..types import StockCheckRequest, StockCheckResult, StockStatus, InventoryCategory
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


class IngredientHandler(BaseInventoryHandler):
    """Handler for ingredient stock checking with FIFO support"""

    def check_availability(self, request: StockCheckRequest, organization_id: int) -> StockCheckResult:
        """
        Check ingredient availability using FIFO entries and unit conversion.

        Process:
        1. Find ingredient in organization
        2. Get available FIFO lots (excludes expired)
        3. Convert between recipe unit and storage unit  
        4. Check if enough stock for planned deduction
        5. Determine status based on availability and low stock settings
        """
        ingredient = InventoryItem.query.filter_by(
            id=request.item_id,
            organization_id=organization_id
        ).first()

        if not ingredient:
            return self._create_not_found_result(request)

        # Get available FIFO lots (excludes expired automatically)
        available_lots = InventoryLot.query.filter(
            InventoryLot.inventory_item_id == ingredient.id,
            InventoryLot.remaining_quantity > 0
        )

        # Filter out expired lots if item is perishable
        if ingredient.is_perishable:
            today = datetime.now().date()
            available_lots = available_lots.filter(
                (InventoryLot.expiration_date == None) | 
                (InventoryLot.expiration_date >= today)
            )

        available_lots = available_lots.order_by(InventoryLot.received_date.asc()).all()
        total_available = sum(lot.remaining_quantity for lot in available_lots)

        stock_unit = ingredient.unit
        recipe_unit = request.unit

        logger.debug(f"Ingredient {ingredient.name}: {total_available} {stock_unit} available, need {request.quantity_needed} {recipe_unit}")

        try:
            conversion_result = ConversionEngine.convert_units(
                amount=float(request.quantity_needed),
                from_unit=recipe_unit,
                to_unit=stock_unit,
                ingredient_id=ingredient.id,
                density=ingredient.density
            )

            if conversion_result['success']:
                # Successful conversion
                available_converted = conversion_result['converted_value']
                conversion_details = {
                    'conversion_type': conversion_result.get('conversion_type', 'unknown'),
                    'density_used': conversion_result.get('density_used'),
                    'requires_attention': conversion_result.get('requires_attention', False)
                }

                # Check if enough stock (planned deduction check)
                status = self._determine_status_with_thresholds(
                    available_converted, 
                    request.quantity_needed,
                    ingredient
                )

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
            else:
                # Handle specific error codes for wall of drawers protocol
                error_code = conversion_result['error_code']
                error_data = conversion_result['error_data']

                # For conversion errors, we still show a table row but mark it as needing attention
                # The drawer protocol will handle fixing the conversion issue
                conversion_details = {
                    'error_code': error_code,
                    'needs_user_attention': True
                }

                if error_code == 'MISSING_DENSITY':
                    conversion_details.update({
                        'error_type': 'missing_density',
                        'ingredient_id': error_data.get('ingredient_id'),
                        'ingredient_name': ingredient.name,
                        'from_unit': error_data.get('from_unit'),
                        'to_unit': error_data.get('to_unit'),
                        'drawer_action': 'open_density_modal',
                        'density_help_link': '/conversion/units'
                    })
                    # Suggest density if available
                    suggested_density = self._get_suggested_density(ingredient.name)
                    if suggested_density:
                        conversion_details['suggested_density'] = suggested_density

                elif error_code == 'MISSING_CUSTOM_MAPPING':
                    conversion_details.update({
                        'error_type': 'missing_custom_mapping',
                        'from_unit': error_data.get('from_unit'),
                        'to_unit': error_data.get('to_unit'),
                        'drawer_action': 'open_unit_mapping_modal',
                        'unit_manager_link': '/conversion/units'
                    })

                elif error_code in ['UNKNOWN_SOURCE_UNIT', 'UNKNOWN_TARGET_UNIT']:
                    conversion_details.update({
                        'error_type': 'unknown_unit',
                        'unknown_unit': error_data.get('unit'),
                        'drawer_action': 'open_unit_creation_modal'
                    })

                elif error_code == 'SYSTEM_ERROR':
                    conversion_details.update({
                        'error_type': 'system_error',
                        'message': 'Unit conversion is not available at the moment, please try again'
                    })

                else:
                    conversion_details.update({
                        'error_type': 'conversion_error',
                        'message': error_data.get('message', 'Conversion failed')
                    })

                # Return a result that shows in the table but indicates conversion error
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
                    status=StockStatus.ERROR,  # Shows as an error status in table
                    error_message=f"Fix conversion: {error_code}",
                    formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                    formatted_available="Fix Conversion",
                    conversion_details=conversion_details
                )

        except ValueError as e:
            # This catch is for unexpected ValueErrors not handled by ConversionEngine's structured response
            error_msg = str(e)
            status = StockStatus.ERROR
            conversion_details = {
                'error_type': 'unexpected_value_error',
                'message': error_msg
            }

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
                error_message=f"Unexpected error during conversion: {error_msg}",
                formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                formatted_available="N/A",
                conversion_details=conversion_details
            )
        except Exception as e:
            # Catch all other unexpected exceptions
            logger.exception(f"An unexpected error occurred during stock check for item {ingredient.id}")
            status = StockStatus.ERROR
            conversion_details = {
                'error_type': 'system_error',
                'message': 'Unit conversion is not available at the moment, please try again'
            }

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
                error_message=conversion_details['message'],
                formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                formatted_available="N/A",
                conversion_details=conversion_details
            )


    def _get_suggested_density(self, ingredient_name: str) -> Optional[float]:
        """Get suggested density for common ingredients based on name"""
        density_suggestions = {
            'beeswax': 0.96,
            'wax': 0.93,
            'honey': 1.42,
            'oil': 0.91,
            'water': 1.0,
            'milk': 1.03,
            'butter': 0.92,
            'cream': 0.994,
            'syrup': 1.37
        }

        ingredient_lower = ingredient_name.lower()
        for key, density in density_suggestions.items():
            if key in ingredient_lower:
                return density
        return None

    def _determine_status_with_thresholds(self, available: float, needed: float, 
                                        ingredient: InventoryItem) -> StockStatus:
        """Determine status considering low stock thresholds"""
        if available >= needed:
            # Have enough, but check if low stock
            if ingredient.low_stock_threshold and available <= ingredient.low_stock_threshold:
                return StockStatus.LOW
            return StockStatus.OK
        elif available > 0:
            return StockStatus.LOW  
        else:
            return StockStatus.NEEDED

    def get_item_details(self, item_id: int, organization_id: int) -> Optional[dict]:
        """Get ingredient details"""
        ingredient = InventoryItem.query.filter_by(
            id=item_id,
            organization_id=organization_id
        ).first()
        if not ingredient:
            return None

        return {
            'id': ingredient.id,
            'name': ingredient.name,
            'unit': ingredient.unit,
            'quantity': ingredient.quantity,
            'cost_per_unit': ingredient.cost_per_unit,
            'density': getattr(ingredient, 'density', None),
            'type': ingredient.type,
            'low_stock_threshold': ingredient.low_stock__threshold
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