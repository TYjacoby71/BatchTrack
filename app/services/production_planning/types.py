
"""
Production Planning Types

Simplified data structures focused on orchestrating recipe → stock → container → batch flow.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ProductionRequest:
    """Request for production planning analysis"""
    recipe_id: int
    scale: float = 1.0
    organization_id: Optional[int] = None


@dataclass
class IngredientRequirement:
    """Individual ingredient requirement from USCS stock check"""
    ingredient_id: int
    ingredient_name: str
    scale: float  # The scale factor applied
    unit: str
    total_cost: float
    status: str  # From USCS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'item_id': self.ingredient_id,
            'item_name': self.ingredient_name,
            'scale': self.scale,
            'unit': self.unit,
            'total_cost': self.total_cost,
            'status': self.status,
            'category': 'ingredient'
        }


@dataclass
class ContainerOption:
    """Available container option for recipe"""
    container_id: int
    container_name: str
    storage_capacity: float
    storage_unit: str
    available_quantity: int
    containers_needed: int
    cost_each: float
    fill_percentage: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'item_id': self.container_id,
            'item_name': self.container_name,
            'storage_capacity': self.storage_capacity,
            'storage_unit': self.storage_unit,
            'available': self.available_quantity,
            'needed': self.containers_needed,
            'cost_each': self.cost_each,
            'fill_percentage': self.fill_percentage,
            'category': 'container'
        }


@dataclass
class ContainerStrategy:
    """Simple container selection result"""
    selected_containers: List[ContainerOption]
    total_containers_needed: int
    total_capacity: float
    average_fill_percentage: float
    waste_percentage: float
    estimated_cost: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'containers': [opt.to_dict() for opt in self.selected_containers],
            'total_containers_needed': self.total_containers_needed,
            'total_capacity': self.total_capacity,
            'average_fill_percentage': self.average_fill_percentage,
            'waste_percentage': self.waste_percentage,
            'estimated_cost': self.estimated_cost
        }


@dataclass
class CostBreakdown:
    """Simple cost analysis"""
    total_ingredient_cost: float
    total_container_cost: float
    total_production_cost: float
    cost_per_unit: float
    yield_amount: float
    yield_unit: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'total_cost': self.total_production_cost,
            'cost_per_unit': self.cost_per_unit,
            'ingredient_cost': self.total_ingredient_cost,
            'container_cost': self.total_container_cost,
            'yield_amount': self.yield_amount,
            'yield_unit': self.yield_unit
        }


@dataclass
class ProductionPlan:
    """Complete production plan for batch handoff"""
    request: ProductionRequest
    feasible: bool
    ingredient_requirements: List[IngredientRequirement]
    projected_yield: Dict[str, Any]
    container_strategy: Optional[ContainerStrategy] = None
    container_options: List[ContainerOption] = field(default_factory=list)
    cost_breakdown: Optional[CostBreakdown] = None
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert production plan to dictionary for API responses"""
        # Build stock results from USCS data (ingredients) + container analysis
        stock_results = []
        
        # Add ingredients from USCS
        for req in self.ingredient_requirements:
            stock_results.append(req.to_dict())
        
        # Add containers from analysis
        for container in self.container_options:
            stock_results.append(container.to_dict())

        return {
            'success': True,
            'feasible': self.feasible,
            'stock_results': stock_results,
            'ingredient_requirements': [req.to_dict() for req in self.ingredient_requirements],
            'container_options': [opt.to_dict() for opt in self.container_options],
            'projected_yield': self.projected_yield,
            'cost_breakdown': self.cost_breakdown.to_dict() if self.cost_breakdown else {},
            'issues': self.issues
        }
