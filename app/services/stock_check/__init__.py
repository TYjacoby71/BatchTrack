"""
Universal Stock Check System (USCS)

A modular system for checking availability across different inventory categories.
Supports ingredients, containers, products, and future categories like consumables.
"""

from .core import UniversalStockCheckService
from .handlers import ContainerHandler, IngredientHandler, ProductHandler
from .types import InventoryCategory, StockCheckRequest, StockCheckResult

# Stock check service package

# Backward compatibility alias
StockCheckService = UniversalStockCheckService


__all__ = [
    "UniversalStockCheckService",
    "StockCheckService",  # Added this for backward compatibility
    "IngredientHandler",
    "ContainerHandler",
    "ProductHandler",
    "StockCheckRequest",
    "StockCheckResult",
    "InventoryCategory",
]
