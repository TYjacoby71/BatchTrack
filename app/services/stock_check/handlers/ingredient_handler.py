"""Ingredient stock check handler.

Synopsis:
Check ingredient availability using FIFO lots and unit conversions.

Glossary:
- Stock check: Availability evaluation for planned usage.
- FIFO lot: Available inventory lot considered in checks.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from app.models import InventoryItem
from app.models.inventory_lot import InventoryLot
from app.services.unit_conversion.unit_conversion import ConversionEngine
from ..types import StockCheckRequest, StockCheckResult, StockStatus, InventoryCategory
from .base_handler import BaseInventoryHandler

logger = logging.getLogger(__name__)


# --- Ingredient stock handler ---
# Purpose: Check ingredient availability using FIFO lots.
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

        # Get available FIFO lots (we will exclude expired below when perishable)
        available_lots = InventoryLot.query.filter(
            InventoryLot.inventory_item_id == ingredient.id,
            InventoryLot.remaining_quantity_base > 0
        )

        # Filter out expired lots if item is perishable
        if ingredient.is_perishable:
            from app.utils.timezone_utils import TimezoneUtils
            now_utc = TimezoneUtils.utc_now()
            # Ensure we compare like with like: store and compare as UTC-aware moments
            available_lots = available_lots.filter(
                (InventoryLot.expiration_date == None) |
                (InventoryLot.expiration_date >= now_utc)
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
                # Convert needed amount to stock units for comparison
                needed_in_stock_units = conversion_result['converted_value']
                
                # Convert available stock to recipe units for display
                stock_to_recipe_result = ConversionEngine.convert_units(
                    amount=float(total_available),
                    from_unit=stock_unit,
                    to_unit=recipe_unit,
                    ingredient_id=ingredient.id,
                    density=ingredient.density
                )
                
                available_in_recipe_units = stock_to_recipe_result['converted_value'] if stock_to_recipe_result['success'] else total_available
                
                conversion_details = {
                    'conversion_type': conversion_result.get('conversion_type', 'unknown'),
                    'density_used': conversion_result.get('density_used'),
                    'requires_attention': conversion_result.get('requires_attention', False)
                }

                # Check if enough stock (compare in stock units)
                # Determine status using available vs needed (both in stock units)
                status = self._determine_status_with_thresholds(
                    available=total_available,
                    needed=needed_in_stock_units,
                    ingredient=ingredient
                )

                return StockCheckResult(
                    item_id=ingredient.id,
                    item_name=ingredient.name,
                    category=InventoryCategory.INGREDIENT,
                    needed_quantity=request.quantity_needed,
                    needed_unit=recipe_unit,
                    available_quantity=available_in_recipe_units,  # Show available in recipe units
                    available_unit=recipe_unit,
                    raw_stock=total_available,
                    stock_unit=stock_unit,
                    status=status,
                    formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                    formatted_available=self._format_quantity_display(available_in_recipe_units, recipe_unit),
                    conversion_details=conversion_details
                )
            else:
                # Conversion failed - ConversionEngine handles its own drawer logic
                # Stock check just reports the conversion error
                conversion_details = {
                    'error_code': conversion_result['error_code'],
                    'requires_attention': conversion_result.get('requires_attention', False),
                    'error_message': conversion_result.get('error_data', {}).get('message', 'Conversion failed')
                }

                # If conversion failed, we can't check stock properly
                if not conversion_result.get('success'):
                    conversion_details['requires_conversion_fix'] = True
                    # Pass through drawer requirements from conversion engine
                    if conversion_result.get('requires_drawer'):
                        conversion_details['requires_drawer'] = True
                    # Pass through drawer payload for universal drawer protocol
                    if conversion_result.get('drawer_payload'):
                        conversion_details['drawer_payload'] = conversion_result.get('drawer_payload')

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
                    error_message=conversion_details['error_message'],
                    formatted_needed=self._format_quantity_display(request.quantity_needed, recipe_unit),
                    formatted_available="Conversion Error",
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
            'low_stock_threshold': ingredient.low_stock_threshold
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