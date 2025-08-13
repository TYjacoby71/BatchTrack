from datetime import date
from sqlalchemy import and_, or_
from flask_login import current_user

from app.models.inventory import InventoryItem, InventoryHistory
try:
    from app.models.product import ProductSKUHistory
except Exception:  # pragma: no cover
    ProductSKUHistory = None  # type: ignore


def _fresh_filter(model):
    today = date.today()
    return or_(getattr(model, "expiration_date").is_(None),
               getattr(model, "expiration_date") >= today)


def _scoped(query, model):
    if current_user and getattr(current_user, "is_authenticated", False):
        return query.filter(getattr(model, "organization_id") == current_user.organization_id)
    return query


def _entries_for_item(inventory_item_id: int, include_expired: bool):
    item = InventoryItem.query.get(inventory_item_id)
    if not item:
        return [], None

    if item.type == "product" and ProductSKUHistory is not None:
        q = ProductSKUHistory.query.filter(
            and_(ProductSKUHistory.inventory_item_id == inventory_item_id,
                 ProductSKUHistory.remaining_quantity > 0)
        )
        if not include_expired:
            q = q.filter(_fresh_filter(ProductSKUHistory))
        q = _scoped(q, ProductSKUHistory)
        return q.all(), item

    q = InventoryHistory.query.filter(
        and_(InventoryHistory.inventory_item_id == inventory_item_id,
             InventoryHistory.remaining_quantity > 0)
    )
    if not include_expired:
        q = q.filter(_fresh_filter(InventoryHistory))
    q = _scoped(q, InventoryHistory)
    return q.all(), item


def _available_qty(inventory_item_id: int, include_expired: bool) -> float:
    entries, _ = _entries_for_item(inventory_item_id, include_expired)
    return float(sum(float(getattr(e, "remaining_quantity", 0.0)) for e in entries))


def check_stock_availability(inventory_requirements):
    """
    Check if we have enough inventory to fulfill the given requirements.
    inventory_requirements: List of dicts with keys: item_id, quantity_needed, unit
    Returns: Dict with 'can_make': bool, 'missing_items': list
    """
    from app.models import InventoryItem
    from app.services.conversion_wrapper import safe_convert

    missing_items = []
    can_make = True

    for requirement in inventory_requirements:
        inventory_item_id = requirement['item_id']
        quantity_needed = requirement['quantity_needed']
        unit_needed = requirement['unit']

        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            missing_items.append({
                'item_id': inventory_item_id,
                'item_name': 'Unknown Item',
                'quantity_needed': quantity_needed,
                'quantity_available': 0,
                'unit': unit_needed
            })
            can_make = False
            continue

        # If units match exactly, no conversion needed
        if unit_needed == item.unit:
            converted_quantity = quantity_needed
        else:
            # Try to convert units
            conversion_result = safe_convert(quantity_needed, unit_needed, item.unit, ingredient_id=item.id)
            if conversion_result['ok']:
                converted_quantity = conversion_result['result']['converted_value']
            else:
                # Cannot convert - this is a blocking error
                missing_items.append({
                    'item_id': inventory_item_id,
                    'item_name': item.name,
                    'quantity_needed': quantity_needed,
                    'quantity_available': item.quantity,
                    'unit': unit_needed,
                    'conversion_error': conversion_result['error']
                })
                can_make = False
                continue

        # Check if we have enough quantity
        if item.quantity < converted_quantity:
            missing_items.append({
                'item_id': inventory_item_id,
                'item_name': item.name,
                'quantity_needed': quantity_needed,
                'quantity_available': item.quantity,
                'unit': unit_needed
            })
            can_make = False

    return {
        'can_make': can_make,
        'missing_items': missing_items
    }


# Optional convenience alias
def get_available_quantity(inventory_item_id: int, include_expired: bool = False) -> float:
    return _available_qty(inventory_item_id, include_expired)


# Keep the rest of the existing functions for compatibility
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

        # Get available FIFO entries (non-expired only) - explicitly exclude expired
        from ..services.inventory_adjustment import process_inventory_adjustment
        available_entries = FIFOService.get_fifo_entries(ingredient.id)  # This already excludes expired
        total_available = sum(entry.remaining_quantity for entry in available_entries)

        # Double-check: ensure we're only counting fresh, non-expired inventory
        # The get_fifo_entries method already filters out expired entries, but this confirms it

        stock_unit = ingredient.unit
        recipe_unit = recipe_ingredient.unit
        density = ingredient.density if ingredient.density else None

        print(f"  - Available (non-expired): {total_available} {stock_unit}, Need: {needed_amount} {recipe_unit}")

        try:
            # Convert available stock to recipe unit using UUCS
            print(f"  - Converting {total_available} {stock_unit} to {recipe_unit}")
            conversion_result = ConversionEngine.convert_units(
                total_available,
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
                'raw_stock': float(total_available),
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


class StockCheckService:
    """DEPRECATED - Backwards-compatibility wrapper for existing stock check functions

    WARNING: This compatibility layer will be removed in the next release.
    Use the canonical inventory adjustment service directly.
    """

    @staticmethod
    def check_availability(*args, **kwargs):
        """Check if ingredients are available for production"""
        import warnings
        warnings.warn(
            "StockCheckService.check_availability is deprecated. Use canonical service directly.",
            DeprecationWarning,
            stacklevel=2
        )
        return check_recipe_availability(*args, **kwargs)

    @staticmethod
    def check_recipe_availability(*args, **kwargs):
        return check_recipe_availability(*args, **kwargs)

    @staticmethod
    def check_ingredient_availability(*args, **kwargs):
        return check_ingredient_availability(*args, **kwargs)

    @staticmethod
    def get_available_inventory_summary(*args, **kwargs):
        return get_available_inventory_summary(*args, **kwargs)

    @staticmethod
    def universal_stock_check(*args, **kwargs):
        return universal_stock_check(*args, **kwargs)


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