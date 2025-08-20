"""
Universal Stock Check System (USCS)

A modular system for checking availability across different inventory categories.
Supports ingredients, containers, products, and future categories like consumables.
"""

from .core import UniversalStockCheckService
from .handlers import IngredientHandler, ContainerHandler, ProductHandler
from .types import StockCheckRequest, StockCheckResult, InventoryCategory

# Stock check service package
from .core import StockCheckService

def check_stock_availability(item_id, required_quantity):
    """Check if sufficient stock is available for an item.

    Args:
        item_id: The inventory item ID
        required_quantity: The quantity needed

    Returns:
        dict: Contains 'available' (bool) and 'current_quantity' (float)
    """
    from app.models.inventory import InventoryItem

    item = InventoryItem.query.get(item_id)
    if not item:
        return {'available': False, 'current_quantity': 0.0}

    return {
        'available': item.quantity >= required_quantity,
        'current_quantity': item.quantity
    }

# Backward compatibility alias
StockCheckService = UniversalStockCheckService


__all__ = [
    'UniversalStockCheckService',
    'StockCheckService', # Added this for backward compatibility
    'IngredientHandler',
    'ContainerHandler',
    'ProductHandler',
    'StockCheckRequest',
    'StockCheckResult',
    'InventoryCategory',
    'check_stock_availability'
]