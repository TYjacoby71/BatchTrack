"""
Type definitions for the Universal Stock Check System
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class InventoryCategory(Enum):
    """Supported inventory categories"""
    INGREDIENT = "ingredient"
    CONTAINER = "container"
    PRODUCT = "product"
    CONSUMABLE = "consumable"  # Future category


class StockStatus(Enum):
    """Stock availability status"""
    AVAILABLE = "AVAILABLE"
    OK = "OK"  # Alias for AVAILABLE
    LOW = "LOW"
    NEEDED = "NEEDED"
    ERROR = "ERROR"
    DENSITY_MISSING = "DENSITY_MISSING"


@dataclass
class StockCheckRequest:
    """Request for stock availability check"""
    item_id: int
    quantity_needed: float
    unit: str
    category: InventoryCategory
    scale_factor: float = 1.0


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
            'item_id': self.item_id,
            'name': self.item_name,
            'type': self.category.value,
            'needed': self.needed_quantity,
            'needed_unit': self.needed_unit,
            'available': self.available_quantity,
            'available_unit': self.available_unit,
            'raw_stock': self.raw_stock,
            'stock_unit': self.stock_unit,
            'status': self.status.value,
            'formatted_needed': self.formatted_needed,
            'formatted_available': self.formatted_available,
            'error': self.error_message,
            'conversion_details': self.conversion_details
        }