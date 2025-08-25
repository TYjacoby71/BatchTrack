"""
Internal Stock Check Service

This service is for internal system use only. 
External applications should not access this directly.
"""

# Internal imports only - no public API
from .core import UniversalStockCheckService
from .types import StockCheckRequest, StockCheckResult, InventoryCategory, StockStatus

__all__ = []  # No public exports