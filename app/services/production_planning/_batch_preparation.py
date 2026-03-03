"""
Batch Preparation for Production Planning

Prepares data structures needed for batch creation from production plans.
Acts as a bridge between production planning and the batch service.
"""

import logging
from typing import Any, Dict

from flask_login import current_user

from .types import ProductionPlan

logger = logging.getLogger(__name__)


def prepare_batch_data(production_plan: ProductionPlan) -> Dict[str, Any]:
    """
    Prepare batch creation data from a production plan.

    Returns data structure suitable for batch service consumption.
    """
    try:
        if not production_plan.feasible:
            raise ValueError(
                "Cannot prepare batch data for non-feasible production plan"
            )

        batch_data = {
            "recipe_id": production_plan.request.recipe_id,
            "scale": production_plan.request.scale,
            "planned_ingredients": [],
            "planned_containers": [],
            "estimated_cost": production_plan.cost_breakdown.total_production_cost,
            "estimated_yield": {
                "amount": production_plan.cost_breakdown.yield_amount,
                "unit": production_plan.cost_breakdown.yield_unit,
            },
            # Include portioning snapshot as part of the canonical plan
            "portioning_data": None,
        }

        # Prepare ingredient data
        for ingredient in production_plan.ingredient_requirements:
            batch_data["planned_ingredients"].append(
                {
                    "inventory_item_id": ingredient.ingredient_id,
                    "quantity_needed": getattr(ingredient, "scaled_quantity", 0),
                    "unit": ingredient.unit,
                    "estimated_cost_per_unit": getattr(ingredient, "cost_per_unit", 0),
                }
            )

        # Prepare container data
        if production_plan.container_strategy:
            for container in production_plan.container_strategy.selected_containers:
                batch_data["planned_containers"].append(
                    {
                        "inventory_item_id": container.container_id,
                        "quantity_needed": container.containers_needed,
                        "estimated_cost_each": container.cost_each,
                    }
                )

        # Include portioning snapshot (raw, scaled) if plan indicates portioned recipe
        try:
            if getattr(production_plan, "portioning", None) and getattr(
                production_plan.portioning, "is_portioned", False
            ):
                # Expect planning to have already scaled these values
                snap = {
                    "is_portioned": True,
                    "portion_name": getattr(
                        production_plan.portioning, "portion_name", None
                    ),
                    "portion_count": getattr(
                        production_plan.portioning, "portion_count", None
                    ),
                    "bulk_yield_quantity": production_plan.cost_breakdown.yield_amount,
                    "bulk_yield_unit": production_plan.cost_breakdown.yield_unit,
                }
                batch_data["portioning_data"] = snap
        except Exception:
            # Do not fail overall plan prep because of optional portioning
            logger.warning("Suppressed exception fallback at app/services/production_planning/_batch_preparation.py:84", exc_info=True)
            pass

        logger.info(
            f"Prepared batch data for recipe {production_plan.request.recipe_id}"
        )
        return batch_data

    except Exception as e:
        logger.error(f"Error preparing batch data: {e}")
        raise


def generate_batch_plan(recipe_id: int, scale: float = 1.0) -> Dict[str, Any]:
    """
    Generate a complete batch plan ready for batch creation.

    This is a convenience function that runs production planning
    and immediately prepares batch data.
    """
    try:
        from ._core import execute_production_planning
        from .types import ProductionRequest

        # Create production request
        request = ProductionRequest(
            recipe_id=recipe_id,
            scale=scale,
            organization_id=(
                current_user.organization_id if current_user.is_authenticated else None
            ),
        )

        # Execute planning
        production_plan = execute_production_planning(request)

        if not production_plan.feasible:
            return {
                "success": False,
                "feasible": False,
                "issues": production_plan.issues,
                "recommendations": production_plan.recommendations,
            }

        # Prepare batch data
        batch_data = prepare_batch_data(production_plan)

        return {
            "success": True,
            "feasible": True,
            "batch_data": batch_data,
            "production_plan": production_plan.to_dict(),
        }

    except Exception as e:
        logger.error(f"Error generating batch plan: {e}")
        return {"success": False, "error": str(e)}
