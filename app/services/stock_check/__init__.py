"""
Universal Stock Check System (USCS)

A modular system for checking availability across different inventory categories.
Supports ingredients, containers, products, and future categories like consumables.
"""

from .core import UniversalStockCheckService
from .handlers import IngredientHandler, ContainerHandler, ProductHandler
from .types import StockCheckRequest, StockCheckResult, InventoryCategory

# Stock check service package
from .core import UniversalStockCheckService

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
    'InventoryCategory'
]