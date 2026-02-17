"""
Stock Check Types

Core data structures for the Universal Stock Check Service.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class InventoryCategory(Enum):
    """Categories of inventory items"""

    INGREDIENT = "ingredient"
    CONTAINER = "container"
    PRODUCT = "product"


class StockStatus(Enum):
    """Stock availability status"""

    OK = "OK"  # Sufficient stock available
    LOW = "LOW"  # Stock below low threshold but available
    NEEDED = "NEEDED"  # Insufficient stock
    OUT_OF_STOCK = "OUT_OF_STOCK"  # No stock available
    ERROR = "ERROR"  # Error checking stock
    DENSITY_MISSING = "DENSITY_MISSING"  # Missing density for conversion


@dataclass
class StockCheckRequest:
    """Request for stock availability check"""

    item_id: int
    quantity_needed: float
    unit: str
    category: InventoryCategory
    organization_id: Optional[int] = None
    recipe_scoping: Optional[List[int]] = None  # For recipe-specific item filtering


@dataclass
class StockCheckResult:
    """Result of stock availability check"""

    item_id: int
    item_name: str
    category: InventoryCategory
    needed_quantity: float
    needed_unit: str
    available_quantity: float
    available_unit: str
    status: StockStatus
    raw_stock: float = 0.0
    stock_unit: str = ""
    formatted_needed: str = ""
    formatted_available: str = ""
    error_message: Optional[str] = None
    conversion_details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "item_id": self.item_id,
            "name": self.item_name,
            "type": self.category.value,
            "needed": self.needed_quantity,
            "needed_unit": self.needed_unit,
            "available": self.available_quantity,
            "available_unit": self.available_unit,
            "raw_stock": self.raw_stock,
            "stock_unit": self.stock_unit,
            "status": self.status.value,
            "formatted_needed": self.formatted_needed,
            "formatted_available": self.formatted_available,
            "error": self.error_message,
            "conversion_details": self.conversion_details,
        }
