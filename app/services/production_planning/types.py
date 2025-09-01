"""
Type definitions for production planning services
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from decimal import Decimal


@dataclass
class ContainerOption:
    """Represents a container option for production planning"""
    container_id: int
    container_name: str
    capacity: float
    capacity_unit: str
    containers_needed: int
    total_capacity: float
    containment_percentage: float
    last_container_fill_percentage: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "container_id": self.container_id,
            "container_name": self.container_name,
            "capacity": self.capacity,
            "capacity_unit": self.capacity_unit,
            "containers_needed": self.containers_needed,
            "total_capacity": self.total_capacity,
            "containment_percentage": round(self.containment_percentage, 2),
            "last_container_fill_percentage": round(self.last_container_fill_percentage, 2)
        }


@dataclass
class ContainerStrategy:
    """Represents a container usage strategy"""
    containers_to_use: List[Dict[str, Any]]
    total_yield_covered: float
    efficiency_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "containers_to_use": self.containers_to_use,
            "total_yield_covered": self.total_yield_covered,
            "efficiency_score": self.efficiency_score
        }


@dataclass class StockCheckResult:
    """Result of stock availability check"""
    ingredient_id: int
    ingredient_name: str
    required_amount: float
    required_unit: str
    available_amount: float
    available_unit: str
    is_sufficient: bool
    shortage_amount: Optional[float] = None
    shortage_unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient_name,
            "required_amount": self.required_amount,
            "required_unit": self.required_unit,
            "available_amount": self.available_amount,
            "available_unit": self.available_unit,
            "is_sufficient": self.is_sufficient,
            "shortage_amount": self.shortage_amount,
            "shortage_unit": self.shortage_unit
        }