from ..models import db, Recipe, InventoryItem, InventoryHistory
from sqlalchemy import or_
from app.services.unit_conversion import ConversionEngine
from flask_login import current_user
from datetime import datetime, timezone

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

        # Get current inventory details - exclude expired FIFO entries using dynamic expiration
        from ..blueprints.expiration.services import ExpirationService
        from ..utils.timezone_utils import TimezoneUtils

        all_fifo_entries = InventoryHistory.query.filter(
            InventoryHistory.inventory_item_id == ingredient.id,
            InventoryHistory.remaining_quantity > 0
        ).all()

        # Filter out expired entries using dynamic expiration calculation
        now_utc = TimezoneUtils.utc_now()
        # Ensure now_utc is timezone-aware for consistent comparison
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        available_fifo_entries = []

        for entry in all_fifo_entries:
            if not entry.is_perishable:
                # Non-perishable items are always available
                available_fifo_entries.append(entry)
            else:
                # Check if perishable item is expired using dynamic calculation
                expiration_date = ExpirationService.get_effective_expiration_date(entry)
                if expiration_date:
                    # Convert to UTC for comparison
                    if expiration_date.tzinfo:
                        expiration_utc = expiration_date.astimezone(timezone.utc)
                    else:
                        expiration_utc = expiration_date.replace(tzinfo=timezone.utc)

                    # Only include if not expired
                    if expiration_utc >= now_utc:
                        available_fifo_entries.append(entry)
                else:
                    # If no expiration date can be calculated, include it
                    available_fifo_entries.append(entry)

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

from app.models import InventoryItem, Recipe, RecipeIngredient
from flask_login import current_user


def check_ingredient_availability(ingredient_id, required_amount, unit_id):
    """
    Check if sufficient inventory exists for an ingredient
    """
    try:
        # Get available inventory for the ingredient
        if current_user and current_user.organization_id:
            inventory_items = InventoryItem.query.filter_by(
                ingredient_id=ingredient_id,
                organization_id=current_user.organization_id
            ).all()
        else:
            return {
                'available': False,
                'error': 'No organization context'
            }

        # Calculate total available quantity
        total_available = sum(item.quantity for item in inventory_items if item.quantity > 0)

        if total_available >= required_amount:
            return {
                'available': True,
                'shortage': 0,
                'available_quantity': total_available
            }
        else:
            return {
                'available': False,
                'shortage': required_amount - total_available,
                'available_quantity': total_available
            }

    except Exception as e:
        return {
            'available': False,
            'error': str(e)
        }


def check_recipe_availability(recipe_id, scale_factor=1.0):
    """
    Check if recipe can be made with current inventory
    """
    try:
        if not current_user or not current_user.organization_id:
            return {
                'can_make': False,
                'error': 'No organization context'
            }

        recipe = Recipe.query.filter_by(
            id=recipe_id,
            organization_id=current_user.organization_id
        ).first()

        if not recipe:
            return {
                'can_make': False,
                'error': 'Recipe not found'
            }

        results = []
        can_make = True

        for recipe_ingredient in recipe.recipe_ingredients:
            required_amount = recipe_ingredient.quantity * scale_factor
            availability = check_ingredient_availability(
                recipe_ingredient.ingredient_id,
                required_amount,
                recipe_ingredient.unit_id
            )

            results.append({
                'ingredient_id': recipe_ingredient.ingredient_id,
                'ingredient_name': recipe_ingredient.ingredient.name,
                'required_amount': required_amount,
                'available_amount': availability.get('available_quantity', 0),
                'shortage': availability.get('shortage', 0),
                'available': availability.get('available', False)
            })

            if not availability.get('available', False):
                can_make = False

        return {
            'can_make': can_make,
            'ingredients': results,
            'scale_factor': scale_factor
        }

    except Exception as e:
        return {
            'can_make': False,
            'error': str(e)
        }


def get_available_inventory_summary():
    """
    Get summary of available inventory across all ingredients
    """
    try:
        if not current_user or not current_user.organization_id:
            return {
                'success': False,
                'error': 'No organization context'
            }

        inventory_items = InventoryItem.query.filter_by(
            organization_id=current_user.organization_id
        ).all()

        summary = {}
        for item in inventory_items:
            ingredient_id = item.ingredient_id
            if ingredient_id not in summary:
                summary[ingredient_id] = {
                    'ingredient_name': item.ingredient.name,
                    'total_quantity': 0,
                    'lot_count': 0
                }

            summary[ingredient_id]['total_quantity'] += item.quantity
            summary[ingredient_id]['lot_count'] += 1

        return {
            'success': True,
            'inventory': list(summary.values())
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }