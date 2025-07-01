from ..models import db, Recipe, InventoryItem, InventoryHistory
from sqlalchemy import or_
from app.services.unit_conversion import ConversionEngine
from flask_login import current_user
from datetime import datetime

def universal_stock_check(recipe, scale=1.0, flex_mode=False):
    """Universal Stock Check Service (USCS) - Ingredients Only"""
    results = []
    all_ok = True

    print(f"Starting stock check for recipe: {recipe.name}, scale: {scale}")
    print(f"Recipe has {len(recipe.recipe_ingredients)} recipe ingredients")

    # Check each ingredient in the recipe
    for recipe_ingredient in recipe.recipe_ingredients:
        ingredient = recipe_ingredient.inventory_item
        print(f"Processing recipe ingredient: {recipe_ingredient.quantity} {recipe_ingredient.unit}")
        
        if not ingredient:
            print(f"  - ERROR: No inventory item linked to recipe ingredient ID {recipe_ingredient.id}")
            continue
            
        print(f"  - Found ingredient: {ingredient.name} (org_id: {ingredient.organization_id})")
        print(f"  - Current user org_id: {current_user.organization_id if current_user.is_authenticated else 'None'}")
        
        # Ensure ingredient belongs to current user's organization
        if not ingredient.belongs_to_user():
            print(f"  - SKIPPING: Ingredient {ingredient.name} doesn't belong to current user's organization")
            continue
            
        print(f"  - Ingredient belongs to user, proceeding with stock check")
        needed_amount = recipe_ingredient.quantity * scale

        # Get current inventory details - exclude expired FIFO entries
        today = datetime.now().date()
        available_fifo_entries = InventoryHistory.query.filter(
            InventoryHistory.inventory_item_id == ingredient.id,
            InventoryHistory.remaining_quantity > 0,
            or_(
                InventoryHistory.expiration_date == None,  # Non-perishable items
                InventoryHistory.expiration_date >= today  # Non-expired perishable items
            )
        ).all()
        
        # Sum up available quantity from non-expired entries
        available = sum(entry.remaining_quantity for entry in available_fifo_entries)
        
        stock_unit = ingredient.unit
        recipe_unit = recipe_ingredient.unit
        density = ingredient.density if ingredient.density else None
        
        print(f"  - Available (non-expired): {available} {stock_unit}, Need: {needed_amount} {recipe_unit}")
        
        try:
            # Convert available stock to recipe unit using UUCS
            print(f"  - Converting {available} {stock_unit} to {recipe_unit}")
            conversion_result = ConversionEngine.convert_units(
                available,
                stock_unit,
                recipe_unit,
                ingredient_id=ingredient.id
            )
            print(f"  - Conversion result: {conversion_result}")
            
            if isinstance(conversion_result, dict):
                available_converted = conversion_result['converted_value']
            else:
                raise ValueError(f"Unexpected conversion result format for {ingredient.name}")

            # Determine status
            if available_converted >= needed_amount:
                status = 'OK'
            elif available_converted >= needed_amount * 0.5:
                status = 'LOW'
                all_ok = False
            else:
                status = 'NEEDED'
                all_ok = False
                
            print(f"  - Status: {status} (available_converted: {available_converted}, needed: {needed_amount})")

            # Append result for this ingredient
            # Ensure consistent numeric formatting
            result_item = {
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': float(needed_amount),
                'needed_unit': recipe_unit,
                'available': float(available_converted),
                'available_unit': recipe_unit,
                'raw_stock': float(available),
                'stock_unit': stock_unit,
                'status': status,
                'formatted_needed': f"{needed_amount:.2f} {recipe_unit}",
                'formatted_available': f"{available_converted:.2f} {recipe_unit}"
            }
            results.append(result_item)
            print(f"  - Added result: {result_item}")

        except ValueError as e:
            print(f"  - Conversion failed: {str(e)}")
            error_msg = f"Cannot convert {recipe_unit} to {stock_unit}"
            status = 'DENSITY_MISSING' if "density" in str(e).lower() else 'ERROR'
            error_result = {
                'type': 'ingredient',
                'name': ingredient.name,
                'needed': needed_amount,
                'needed_unit': recipe_unit,
                'available': 0,
                'available_unit': recipe_unit,
                'status': status,
                'error': str(e)
            }
            results.append(error_result)
            print(f"  - Added error result: {error_result}")
            all_ok = False

    print(f"Stock check complete. Found {len(results)} results, all_ok: {all_ok}")
    return {
        'stock_check': results,
        'all_ok': all_ok
    }