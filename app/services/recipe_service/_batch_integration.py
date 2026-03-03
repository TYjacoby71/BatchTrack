"""
Recipe-Batch Integration Operations

Handles the integration between recipes and batch production.
"""

import logging
from typing import Any, Dict

from ...extensions import db
from ...models import Batch, Recipe

logger = logging.getLogger(__name__)


def prepare_batch_from_recipe(
    recipe_id: int, scale: float = 1.0, batch_name: str = None
) -> Dict[str, Any]:
    """
    Prepare batch data from a recipe.

    Args:
        recipe_id: Recipe to base batch on
        scale: Scaling factor for batch
        batch_name: Optional batch name

    Returns:
        Dict with batch preparation data
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return {"success": False, "error": "Recipe not found"}
        if not recipe.predicted_yield or recipe.predicted_yield <= 0:
            return {"success": False, "error": "Recipe has no predicted yield"}

        # Generate batch name if not provided
        if not batch_name:
            batch_name = f"Batch from {recipe.name}"

        # Prepare ingredient list for batch
        batch_ingredients = []
        for recipe_ingredient in recipe.recipe_ingredients:
            scaled_quantity = recipe_ingredient.quantity * scale

            batch_ingredients.append(
                {
                    "inventory_item_id": recipe_ingredient.inventory_item_id,
                    "quantity": scaled_quantity,
                    "unit": recipe_ingredient.unit,
                    "ingredient_name": recipe_ingredient.inventory_item.name,
                }
            )

        return {
            "success": True,
            "recipe_id": recipe_id,
            "batch_name": batch_name,
            "scale": scale,
            "expected_yield": recipe.predicted_yield * scale,
            "yield_unit": recipe.predicted_yield_unit,
            "ingredients": batch_ingredients,
            "instructions": recipe.instructions,
        }

    except Exception as e:
        logger.error(f"Error preparing batch from recipe {recipe_id}: {e}")
        return {"success": False, "error": str(e)}


def update_recipe_from_batch(
    recipe_id: int, batch_id: int, update_yield: bool = True
) -> Dict[str, Any]:
    """
    Update recipe based on actual batch results.

    Args:
        recipe_id: Recipe to update
        batch_id: Batch with actual results
        update_yield: Whether to update recipe yield

    Returns:
        Dict with update results
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        batch = db.session.get(Batch, batch_id)

        if not recipe:
            return {"success": False, "error": "Recipe not found"}

        if not batch:
            return {"success": False, "error": "Batch not found"}

        updates_made = []

        # Update yield if requested and batch is complete
        if update_yield and batch.status == "completed" and batch.actual_yield:
            old_yield = recipe.yield_amount
            recipe.yield_amount = batch.actual_yield
            updates_made.append(
                f"Yield updated from {old_yield} to {batch.actual_yield}"
            )

        if updates_made:
            db.session.commit()
            logger.info(
                f"Updated recipe {recipe_id} from batch {batch_id}: {', '.join(updates_made)}"
            )

        return {
            "success": True,
            "recipe_id": recipe_id,
            "batch_id": batch_id,
            "updates_made": updates_made,
        }

    except Exception as e:
        logger.warning("Suppressed exception fallback at app/services/recipe_service/_batch_integration.py:118", exc_info=True)
        db.session.rollback()
        logger.error(f"Error updating recipe from batch: {e}")
        return {"success": False, "error": str(e)}


def sync_recipe_batch_data(recipe_id: int) -> Dict[str, Any]:
    """
    Sync recipe data with completed batches.

    Args:
        recipe_id: Recipe to sync

    Returns:
        Dict with sync results
    """
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return {"success": False, "error": "Recipe not found"}

        # Find completed batches for this recipe
        completed_batches = Batch.query.filter_by(
            recipe_id=recipe_id, status="completed"
        ).all()

        if not completed_batches:
            return {
                "success": True,
                "message": "No completed batches found for sync",
                "batches_analyzed": 0,
            }

        # Calculate average yield from completed batches
        total_yield = sum(batch.actual_yield or 0 for batch in completed_batches)
        avg_yield = total_yield / len(completed_batches)

        sync_results = {
            "success": True,
            "recipe_id": recipe_id,
            "batches_analyzed": len(completed_batches),
            "current_yield": recipe.yield_amount,
            "calculated_avg_yield": avg_yield,
            "sync_recommended": abs(recipe.yield_amount - avg_yield) > 0.1,
        }

        return sync_results

    except Exception as e:
        logger.error(f"Error syncing recipe-batch data: {e}")
        return {"success": False, "error": str(e)}
