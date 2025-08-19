
"""
Universal Stock Check System (USCS)

A modular system for checking availability across different inventory categories.
Supports ingredients, containers, products, and future categories like consumables.
"""

from .core import UniversalStockCheckService
from .handlers import IngredientHandler, ContainerHandler, ProductHandler
from .types import StockCheckRequest, StockCheckResult, InventoryCategory, StockStatus

# Main service class - this is what everyone should import
USCS = UniversalStockCheckService

__all__ = [
    'UniversalStockCheckService',
    'USCS',  # Short alias
    'IngredientHandler', 
    'ContainerHandler',
    'ProductHandler',
    'StockCheckRequest',
    'StockCheckResult', 
    'InventoryCategory',
    'StockStatus'
]
