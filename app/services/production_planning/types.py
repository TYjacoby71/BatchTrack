
"""
Type definitions for production planning services
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from decimal import Decimal


@dataclass
class ProductionRequest:
    """Request for production planning"""
    recipe_id: int
    scale: float = 1.0
    organization_id: Optional[int] = None
    preferred_container_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "scale": self.scale,
            "organization_id": self.organization_id,
            "preferred_container_id": self.preferred_container_id
        }


@dataclass
class IngredientRequirement:
    """Represents an ingredient requirement for production"""
    ingredient_id: int
    ingredient_name: str
    required_quantity: float
    unit: str
    available_quantity: float = 0.0
    status: str = "unknown"  # available, insufficient, unavailable
    shortage: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient_name,
            "required_quantity": self.required_quantity,
            "unit": self.unit,
            "available_quantity": self.available_quantity,
            "status": self.status,
            "shortage": self.shortage
        }


@dataclass
class CostBreakdown:
    """Cost analysis for production"""
    ingredient_costs: float = 0.0
    container_costs: float = 0.0
    total_production_cost: float = 0.0
    cost_per_unit: float = 0.0
    yield_amount: float = 0.0
    yield_unit: str = "count"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ingredient_costs": self.ingredient_costs,
            "container_costs": self.container_costs,
            "total_production_cost": self.total_production_cost,
            "cost_per_unit": self.cost_per_unit,
            "yield_amount": self.yield_amount,
            "yield_unit": self.yield_unit
        }


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


@dataclass
class ProductionPlan:
    """Complete production plan result"""
    request: ProductionRequest
    feasible: bool
    ingredient_requirements: List[IngredientRequirement]
    projected_yield: Dict[str, Any]
    container_strategy: Optional[ContainerStrategy] = None
    container_options: List[ContainerOption] = None
    cost_breakdown: Optional[CostBreakdown] = None
    issues: List[str] = None
    recommendations: List[str] = None

    def __post_init__(self):
        if self.container_options is None:
            self.container_options = []
        if self.issues is None:
            self.issues = []
        if self.recommendations is None:
            self.recommendations = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "feasible": self.feasible,
            "ingredient_requirements": [req.to_dict() for req in self.ingredient_requirements],
            "projected_yield": self.projected_yield,
            "container_strategy": self.container_strategy.to_dict() if self.container_strategy else None,
            "container_options": [opt.to_dict() for opt in self.container_options],
            "cost_breakdown": self.cost_breakdown.to_dict() if self.cost_breakdown else None,
            "issues": self.issues,
            "recommendations": self.recommendations
        }


@dataclass
class StockCheckResult:
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
