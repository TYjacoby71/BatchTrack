
from ..models import InventoryItem, Recipe, BatchIngredient, ExtraBatchIngredient, Batch
from .unit_conversion import ConversionEngine

class StockCheckService:
    """Service for checking ingredient stock against recipe requirements"""
    
    @staticmethod
    def check_recipe_stock(recipe_id, batch_multiplier=1.0):
        """
        Check if there's enough stock to make a recipe
        
        Args:
            recipe_id: ID of the recipe to check
            batch_multiplier: Multiplier for scaling the recipe
            
        Returns:
            dict: Stock check results with availability and shortages
        """
        try:
            recipe = Recipe.query.get_or_404(recipe_id)
            
            results = {
                "recipe_id": recipe_id,
                "recipe_name": recipe.name,
                "batch_multiplier": batch_multiplier,
                "can_make": True,
                "ingredients": [],
                "shortages": [],
                "total_ingredients": 0,
                "available_ingredients": 0
            }
            
            # Check each ingredient in the recipe
            for recipe_ingredient in recipe.ingredients:
                ingredient_check = StockCheckService._check_ingredient_availability(
                    recipe_ingredient.ingredient_id,
                    recipe_ingredient.quantity * batch_multiplier,
                    recipe_ingredient.unit
                )
                
                ingredient_check["recipe_quantity"] = recipe_ingredient.quantity
                ingredient_check["recipe_unit"] = recipe_ingredient.unit
                ingredient_check["needed_quantity"] = recipe_ingredient.quantity * batch_multiplier
                
                results["ingredients"].append(ingredient_check)
                results["total_ingredients"] += 1
                
                if ingredient_check["available"]:
                    results["available_ingredients"] += 1
                else:
                    results["can_make"] = False
                    results["shortages"].append(ingredient_check)
            
            return results
            
        except Exception as e:
            return {
                "error": f"Error checking recipe stock: {str(e)}",
                "can_make": False
            }

    @staticmethod
    def check_batch_stock(batch_id):
        """
        Check stock for an existing batch including extra ingredients
        
        Args:
            batch_id: ID of the batch to check
            
        Returns:
            dict: Stock check results
        """
        try:
            batch = Batch.query.get_or_404(batch_id)
            
            results = {
                "batch_id": batch_id,
                "batch_name": f"{batch.recipe.name} - Batch {batch.batch_number}",
                "can_make": True,
                "recipe_ingredients": [],
                "extra_ingredients": [],
                "shortages": [],
                "total_ingredients": 0,
                "available_ingredients": 0
            }
            
            # Check recipe ingredients
            if batch.recipe:
                multiplier = batch.batch_multiplier or 1.0
                for recipe_ingredient in batch.recipe.ingredients:
                    ingredient_check = StockCheckService._check_ingredient_availability(
                        recipe_ingredient.ingredient_id,
                        recipe_ingredient.quantity * multiplier,
                        recipe_ingredient.unit
                    )
                    
                    ingredient_check["recipe_quantity"] = recipe_ingredient.quantity
                    ingredient_check["recipe_unit"] = recipe_ingredient.unit
                    ingredient_check["needed_quantity"] = recipe_ingredient.quantity * multiplier
                    ingredient_check["source"] = "recipe"
                    
                    results["recipe_ingredients"].append(ingredient_check)
                    results["total_ingredients"] += 1
                    
                    if ingredient_check["available"]:
                        results["available_ingredients"] += 1
                    else:
                        results["can_make"] = False
                        results["shortages"].append(ingredient_check)
            
            # Check extra ingredients
            extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch_id).all()
            for extra in extra_ingredients:
                ingredient_check = StockCheckService._check_ingredient_availability(
                    extra.ingredient_id,
                    extra.quantity,
                    extra.unit
                )
                
                ingredient_check["needed_quantity"] = extra.quantity
                ingredient_check["needed_unit"] = extra.unit
                ingredient_check["source"] = "extra"
                ingredient_check["notes"] = extra.notes
                
                results["extra_ingredients"].append(ingredient_check)
                results["total_ingredients"] += 1
                
                if ingredient_check["available"]:
                    results["available_ingredients"] += 1
                else:
                    results["can_make"] = False
                    results["shortages"].append(ingredient_check)
            
            return results
            
        except Exception as e:
            return {
                "error": f"Error checking batch stock: {str(e)}",
                "can_make": False
            }

    @staticmethod
    def _check_ingredient_availability(ingredient_id, needed_quantity, needed_unit):
        """
        Check if there's enough of a specific ingredient
        
        Args:
            ingredient_id: ID of the ingredient
            needed_quantity: Quantity needed
            needed_unit: Unit of the needed quantity
            
        Returns:
            dict: Availability information
        """
        try:
            ingredient = InventoryItem.query.get(ingredient_id)
            if not ingredient:
                return {
                    "ingredient_id": ingredient_id,
                    "ingredient_name": "Unknown Ingredient",
                    "available": False,
                    "error": "Ingredient not found"
                }
            
            result = {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient.name,
                "available_quantity": ingredient.quantity,
                "available_unit": ingredient.unit,
                "needed_quantity": needed_quantity,
                "needed_unit": needed_unit,
                "available": False,
                "shortage_amount": 0,
                "can_convert": False,
                "converted_available": None,
                "converted_needed": None,
                "conversion_error": None
            }
            
            # Try to convert units if different
            if ingredient.unit != needed_unit:
                try:
                    # Convert available quantity to needed unit
                    converted_available = ConversionEngine.convert_units(
                        ingredient.quantity,
                        ingredient.unit,
                        needed_unit,
                        ingredient_id=ingredient_id
                    )
                    
                    result["can_convert"] = True
                    result["converted_available"] = converted_available
                    result["converted_needed"] = needed_quantity
                    
                    # Check availability with converted units
                    if converted_available >= needed_quantity:
                        result["available"] = True
                    else:
                        result["shortage_amount"] = needed_quantity - converted_available
                        
                except Exception as e:
                    result["conversion_error"] = str(e)
                    # Fall back to comparing in original units if conversion fails
                    result["available"] = False
                    result["shortage_amount"] = needed_quantity  # Full amount since we can't convert
            else:
                # Same units, direct comparison
                result["can_convert"] = True
                result["converted_available"] = ingredient.quantity
                result["converted_needed"] = needed_quantity
                
                if ingredient.quantity >= needed_quantity:
                    result["available"] = True
                else:
                    result["shortage_amount"] = needed_quantity - ingredient.quantity
            
            return result
            
        except Exception as e:
            return {
                "ingredient_id": ingredient_id,
                "ingredient_name": "Error",
                "available": False,
                "error": f"Error checking availability: {str(e)}"
            }

    @staticmethod
    def get_shortage_suggestions(shortages):
        """
        Get suggestions for addressing ingredient shortages
        
        Args:
            shortages: List of shortage information from stock check
            
        Returns:
            list: Suggestions for addressing shortages
        """
        suggestions = []
        
        for shortage in shortages:
            ingredient_id = shortage.get("ingredient_id")
            if not ingredient_id:
                continue
                
            ingredient = InventoryItem.query.get(ingredient_id)
            if not ingredient:
                continue
            
            suggestion = {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient.name,
                "shortage_amount": shortage.get("shortage_amount", 0),
                "shortage_unit": shortage.get("needed_unit"),
                "suggestions": []
            }
            
            # Check if there are alternative units available
            if shortage.get("conversion_error"):
                suggestion["suggestions"].append({
                    "type": "unit_conversion",
                    "message": f"Unit conversion failed: {shortage['conversion_error']}",
                    "action": "Check unit mappings or add custom conversion"
                })
            
            # Check for low stock threshold
            if ingredient.low_stock_threshold and ingredient.quantity <= ingredient.low_stock_threshold:
                suggestion["suggestions"].append({
                    "type": "low_stock",
                    "message": f"Ingredient is at or below low stock threshold ({ingredient.low_stock_threshold})",
                    "action": "Reorder ingredient"
                })
            
            # Check for partial availability
            if shortage.get("converted_available") and shortage["converted_available"] > 0:
                percentage_available = (shortage["converted_available"] / shortage["converted_needed"]) * 100
                suggestion["suggestions"].append({
                    "type": "partial_availability",
                    "message": f"Only {percentage_available:.1f}% of needed quantity is available",
                    "action": f"Consider reducing batch size or sourcing additional {ingredient.name}"
                })
            
            # Check for substitutes (if ingredient has tags)
            if ingredient.tags:
                similar_ingredients = InventoryItem.query.filter(
                    InventoryItem.id != ingredient_id,
                    InventoryItem.tags.overlap(ingredient.tags)
                ).filter(InventoryItem.quantity > 0).all()
                
                if similar_ingredients:
                    suggestion["suggestions"].append({
                        "type": "substitutes",
                        "message": f"Found {len(similar_ingredients)} ingredients with similar tags",
                        "action": "Consider substitutes: " + ", ".join([ing.name for ing in similar_ingredients[:3]])
                    })
            
            suggestions.append(suggestion)
        
        return suggestions

    @staticmethod
    def bulk_stock_check(recipe_ids, batch_multipliers=None):
        """
        Check stock for multiple recipes at once
        
        Args:
            recipe_ids: List of recipe IDs to check
            batch_multipliers: Optional dict of {recipe_id: multiplier}
            
        Returns:
            dict: Results for all recipes
        """
        try:
            if batch_multipliers is None:
                batch_multipliers = {}
            
            results = {
                "total_recipes": len(recipe_ids),
                "can_make_all": True,
                "recipes": [],
                "consolidated_shortages": {},
                "total_shortages": 0
            }
            
            # Check each recipe
            for recipe_id in recipe_ids:
                multiplier = batch_multipliers.get(recipe_id, 1.0)
                recipe_result = StockCheckService.check_recipe_stock(recipe_id, multiplier)
                results["recipes"].append(recipe_result)
                
                if not recipe_result.get("can_make", False):
                    results["can_make_all"] = False
                
                # Consolidate shortages across all recipes
                for shortage in recipe_result.get("shortages", []):
                    ingredient_id = shortage.get("ingredient_id")
                    if ingredient_id:
                        if ingredient_id not in results["consolidated_shortages"]:
                            results["consolidated_shortages"][ingredient_id] = {
                                "ingredient_name": shortage.get("ingredient_name"),
                                "total_shortage": 0,
                                "recipes_affected": []
                            }
                        
                        results["consolidated_shortages"][ingredient_id]["total_shortage"] += shortage.get("shortage_amount", 0)
                        results["consolidated_shortages"][ingredient_id]["recipes_affected"].append({
                            "recipe_id": recipe_id,
                            "shortage_amount": shortage.get("shortage_amount", 0)
                        })
            
            results["total_shortages"] = len(results["consolidated_shortages"])
            
            return results
            
        except Exception as e:
            return {
                "error": f"Error in bulk stock check: {str(e)}",
                "can_make_all": False
            }
