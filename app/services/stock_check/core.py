"""
Universal Stock Check Service (USCS)

Core service for stock availability checking with three levels:
1. Single item stock check (core function)
2. Recipe stock check (groups single items)
3. Bulk recipe check (groups multiple recipes)

Integrates with FIFO operations and unit conversion engine.
"""

import logging
from typing import Any, Dict, List

from flask_login import current_user

from app.utils.recipe_display import format_recipe_lineage_name

from .handlers import ContainerHandler, IngredientHandler, ProductHandler
from .types import InventoryCategory, StockCheckRequest, StockCheckResult, StockStatus

# FIFOService functionality moved to inventory_adjustment service

logger = logging.getLogger(__name__)


class UniversalStockCheckService:
    """
    Universal Stock Check Service (USCS)

    Provides three levels of stock checking:
    1. check_single_item() - Core function for individual inventory items
    2. check_recipe_stock() - Groups single item checks for a recipe
    3. check_bulk_recipes() - Groups multiple recipe checks
    """

    def __init__(self):
        self.handlers = {
            InventoryCategory.INGREDIENT: IngredientHandler(),
            InventoryCategory.CONTAINER: ContainerHandler(),
            InventoryCategory.PRODUCT: ProductHandler(),
        }

    def _get_organization_id(self) -> int:
        """Get organization ID from current user"""
        if (
            current_user
            and current_user.is_authenticated
            and current_user.organization_id
        ):
            return current_user.organization_id
        else:
            raise ValueError("No organization context available for stock check")

    def check_single_item(
        self,
        item_id: int,
        quantity_needed: float,
        unit: str,
        category: InventoryCategory,
    ) -> StockCheckResult:
        """
        Core function: Check stock for a single inventory item.

        Process:
        1. Find the item in the requested category
        2. Match item with inventory
        3. Convert requested amount to inventory storage unit
        4. Process planned deduction (check if enough stock)
        5. Convert results back to recipe units
        6. Determine stock status (good/low/needed)

        Args:
            item_id: Inventory item ID
            quantity_needed: Amount needed
            unit: Unit of the needed amount
            category: Item category (ingredient/container/product)

        Returns:
            Stock check result with availability status
        """
        try:
            org_id = self._get_organization_id()

            # Get appropriate handler for the category
            handler = self.handlers.get(category)
            if not handler:
                return self._create_error_result(
                    item_id,
                    f"No handler for category: {category}",
                    quantity_needed,
                    unit,
                )

            # Create request object
            request = StockCheckRequest(
                item_id=item_id,
                quantity_needed=quantity_needed,
                unit=unit,
                category=category,
                organization_id=org_id,
            )

            # Handler performs category-specific stock checking
            result = handler.check_availability(request, org_id)

            return result

        except Exception as e:
            logger.error(f"Error in check_single_item: {e}")
            return self._create_error_result(item_id, str(e), quantity_needed, unit)

    def check_recipe_stock(self, recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
        """
        Recipe-level stock check: Groups single item checks for all recipe ingredients.

        Args:
            recipe_id: Recipe ID to check
            scale: Scale factor for the recipe (batch size multiplier)

        Returns:
            Dictionary with overall recipe stock status and individual item results
        """
        try:
            from ...models import Recipe

            org_id = self._get_organization_id()

            recipe = Recipe.query.filter_by(
                id=recipe_id, organization_id=org_id
            ).first()

            if not recipe:
                return {
                    "success": False,
                    "status": "error",
                    "error": "Recipe not found",
                    "stock_check": [],
                }

            if not recipe.recipe_ingredients:
                logger.warning(f"USCS: Recipe {recipe_id} has no ingredients defined")
                return {
                    "success": True,
                    "status": "no_ingredients",
                    "stock_check": [],
                    "message": "Recipe has no ingredients to check",
                }

            # Perform single item checks for all recipe ingredients
            stock_results = []
            has_insufficient = False
            has_low_stock = False
            has_errors = False  # Track if any item check resulted in an error
            conversion_alerts = []
            bubbled_drawer_payload = None

            for recipe_ingredient in recipe.recipe_ingredients:
                # Scale the quantity needed
                scaled_quantity = recipe_ingredient.quantity * scale

                # Check single item stock
                result = self.check_single_item(
                    item_id=recipe_ingredient.inventory_item_id,
                    quantity_needed=scaled_quantity,
                    unit=recipe_ingredient.unit,
                    category=InventoryCategory.INGREDIENT,
                )

                # Convert to dict for response
                result_dict = {
                    "item_id": result.item_id,
                    "item_name": result.item_name,
                    "needed_quantity": result.needed_quantity,
                    "needed_unit": result.needed_unit,
                    "available_quantity": result.available_quantity,
                    "available_unit": result.available_unit,
                    "status": result.status.value,
                    "formatted_needed": result.formatted_needed,
                    "formatted_available": result.formatted_available,
                    "category": result.category.value,
                    "item_type": getattr(
                        recipe_ingredient.inventory_item, "type", result.category.value
                    ),
                }

                if hasattr(result, "error_message") and result.error_message:
                    result_dict["error_message"] = result.error_message
                    has_errors = True  # Mark that an error occurred

                if hasattr(result, "conversion_details") and result.conversion_details:
                    result_dict["conversion_details"] = result.conversion_details

                    # Collect conversion alerts
                    if result.conversion_details.get("needs_unit_mapping"):
                        conversion_alerts.append(
                            {
                                "item_name": result.item_name,
                                "message": f"Custom unit mapping needed for {result.item_name}",
                                "unit_manager_link": result.conversion_details.get(
                                    "unit_manager_link"
                                ),
                            }
                        )

                    # Bubble up drawer payload to top-level if present
                    if not bubbled_drawer_payload and result.conversion_details.get(
                        "drawer_payload"
                    ):
                        bubbled_drawer_payload = result.conversion_details.get(
                            "drawer_payload"
                        )

                stock_results.append(result_dict)

                # Track overall status
                if result.status in [StockStatus.NEEDED, StockStatus.OUT_OF_STOCK]:
                    has_insufficient = True
                elif result.status == StockStatus.LOW:
                    has_low_stock = True

            # Also check consumables if defined on the recipe
            if hasattr(recipe, "recipe_consumables") and recipe.recipe_consumables:
                for rc in recipe.recipe_consumables:
                    scaled_quantity = rc.quantity * scale

                    result = self.check_single_item(
                        item_id=rc.inventory_item_id,
                        quantity_needed=scaled_quantity,
                        unit=rc.unit,
                        category=InventoryCategory.INGREDIENT,
                    )

                    result_dict = {
                        "item_id": result.item_id,
                        "item_name": result.item_name,
                        "needed_quantity": result.needed_quantity,
                        "needed_unit": result.needed_unit,
                        "available_quantity": result.available_quantity,
                        "available_unit": result.available_unit,
                        "status": result.status.value,
                        "formatted_needed": result.formatted_needed,
                        "formatted_available": result.formatted_available,
                        # Override category/type so downstream gating can distinguish
                        "category": "consumable",
                        "item_type": "consumable",
                    }

                    if hasattr(result, "error_message") and result.error_message:
                        result_dict["error_message"] = result.error_message
                        has_errors = True

                    if (
                        hasattr(result, "conversion_details")
                        and result.conversion_details
                    ):
                        result_dict["conversion_details"] = result.conversion_details
                        if result.conversion_details.get("needs_unit_mapping"):
                            conversion_alerts.append(
                                {
                                    "item_name": result.item_name,
                                    "message": f"Custom unit mapping needed for {result.item_name}",
                                    "unit_manager_link": result.conversion_details.get(
                                        "unit_manager_link"
                                    ),
                                }
                            )
                        if (
                            not bubbled_drawer_payload
                            and result.conversion_details.get("drawer_payload")
                        ):
                            bubbled_drawer_payload = result.conversion_details.get(
                                "drawer_payload"
                            )

                    stock_results.append(result_dict)

                    if result.status in [StockStatus.NEEDED, StockStatus.OUT_OF_STOCK]:
                        has_insufficient = True
                    elif result.status == StockStatus.LOW:
                        has_low_stock = True

            # Determine overall recipe status
            if has_errors:
                overall_status = "error"
            elif has_insufficient:
                overall_status = "insufficient_ingredients"
            elif has_low_stock:
                overall_status = "low_stock"
            else:
                overall_status = "ok"

            # Simple response - conversion errors with drawer payloads will be handled by frontend
            all_available = not (has_insufficient or has_errors)

            response = {
                "success": True,
                "status": overall_status,
                "all_ok": all_available,
                "stock_check": stock_results,
                "recipe_name": format_recipe_lineage_name(recipe),
                "error": None,
            }

            # Add conversion alerts if any (but not drawer-required ones)
            if conversion_alerts:
                response["conversion_alerts"] = conversion_alerts

            # Include drawer payload if we have one and ensure retry is configured
            if bubbled_drawer_payload:
                # Ensure a retry operation is provided for the universal handler
                if not (
                    bubbled_drawer_payload.get("retry")
                    or bubbled_drawer_payload.get("retry_operation")
                ):
                    bubbled_drawer_payload["retry"] = {
                        "mode": "frontend_callback",
                        "operation": "stock_check",
                        "data": {"recipe_id": recipe.id, "scale": scale},
                    }
                response["drawer_payload"] = bubbled_drawer_payload

            return response

        except Exception as e:
            logger.error(f"Error in check_recipe_stock: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "stock_check": [],
            }

    def check_bulk_recipes(
        self, recipe_configs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Bulk-level stock check: Groups multiple recipe checks.

        Args:
            recipe_configs: List of dicts with keys: recipe_id, scale

        Returns:
            Dictionary with results for each recipe
        """
        try:
            results = {}

            for config in recipe_configs:
                recipe_id = config.get("recipe_id")
                scale = config.get("scale", 1.0)

                if not recipe_id:
                    results[str(recipe_id)] = {
                        "success": False,
                        "error": "Recipe ID missing",
                    }
                    continue

                # Use recipe-level check
                recipe_result = self.check_recipe_stock(recipe_id, scale)
                results[str(recipe_id)] = recipe_result

            return {"success": True, "results": results}

        except Exception as e:
            logger.error(f"Error in check_bulk_recipes: {e}")
            return {"success": False, "error": str(e)}

    def _create_error_result(
        self, item_id: int, error_message: str, quantity_needed: float, unit: str
    ) -> StockCheckResult:
        """Create standardized error result"""
        return StockCheckResult(
            item_id=item_id,
            item_name="Unknown Item",
            category=InventoryCategory.INGREDIENT,
            needed_quantity=quantity_needed,
            needed_unit=unit,
            available_quantity=0,
            available_unit=unit,
            status=StockStatus.ERROR,
            error_message=error_message,
            formatted_needed=f"{quantity_needed} {unit}",
            formatted_available="0",
        )
