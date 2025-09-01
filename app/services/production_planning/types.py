
"""
Production Planning Types

Core data structures for the production planning service package.
Provides typed interfaces for all production planning operations.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from enum import Enum


class ProductionStatus(Enum):
    """Status of production planning analysis"""
    FEASIBLE = "feasible"
    INSUFFICIENT_STOCK = "insufficient_stock" 
    NO_CONTAINERS = "no_containers"
    ERROR = "error"


@dataclass
class ProductionRequest:
    """Request for production planning analysis"""
    recipe_id: int
    scale: float = 1.0
    organization_id: Optional[int] = None
    preferred_container_id: Optional[int] = None
    max_cost_per_unit: Optional[float] = None
    
    def __post_init__(self):
        if self.scale <= 0:
            raise ValueError("Scale must be positive")


@dataclass
class IngredientRequirement:
    """Requirement for a single ingredient in production"""
    ingredient_id: int
    ingredient_name: str
    required_quantity: float
    required_unit: str
    available_quantity: float
    available_unit: str
    status: str  # 'available', 'insufficient', 'unavailable'
    shortage: float = 0.0
    cost_per_unit: float = 0.0
    total_cost: float = 0.0
    
    @property
    def is_available(self) -> bool:
        return self.status == 'available'


@dataclass
class ContainerOption:
    """A single container option with calculated metrics"""
    container_id: int
    container_name: str
    capacity: float  # Storage capacity in recipe yield units
    available_quantity: int  # How many are in stock
    containers_needed: int  # How many needed for this recipe
    cost_each: float = 0.0
    fill_percentage: float = 0.0  # How full the last container will be
    total_capacity: float = 0.0  # Total capacity if using all needed containers
    
    def __post_init__(self):
        if self.containers_needed > 0:
            self.total_capacity = self.capacity * self.containers_needed
            

@dataclass
class ContainerStrategy:
    """Complete container strategy for production"""
    selected_containers: List[ContainerOption]
    total_capacity: float
    containment_percentage: float  # % of yield that can be contained
    is_complete: bool = False  # True if 100% containment achieved
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.is_complete = self.containment_percentage >= 100.0


@dataclass
class CostBreakdown:
    """Detailed cost analysis for production"""
    ingredient_costs: float = 0.0
    container_costs: float = 0.0
    total_cost: float = 0.0
    cost_per_unit: float = 0.0
    yield_amount: float = 0.0
    yield_unit: str = "units"
    
    def __post_init__(self):
        self.total_cost = self.ingredient_costs + self.container_costs
        if self.yield_amount > 0:
            self.cost_per_unit = self.total_cost / self.yield_amount
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ingredient_costs': float(self.ingredient_costs),
            'container_costs': float(self.container_costs), 
            'total_cost': float(self.total_cost),
            'cost_per_unit': float(self.cost_per_unit),
            'yield_amount': float(self.yield_amount),
            'yield_unit': self.yield_unit
        }


@dataclass
class ProductionPlan:
    """Complete production plan with all analysis results"""
    request: ProductionRequest
    feasible: bool
    ingredient_requirements: List[IngredientRequirement]
    projected_yield: Dict[str, Union[float, str]]
    container_strategy: Optional[ContainerStrategy] = None
    container_options: List[ContainerOption] = field(default_factory=list)
    cost_breakdown: Optional[CostBreakdown] = None
    issues: List[str] = field(default_factory=list)
    status: ProductionStatus = ProductionStatus.FEASIBLE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'success': self.feasible,
            'feasible': self.feasible,
            'recipe_id': self.request.recipe_id,
            'scale': self.request.scale,
            'projected_yield': self.projected_yield,
            'ingredient_requirements': [
                {
                    'ingredient_id': req.ingredient_id,
                    'ingredient_name': req.ingredient_name,
                    'required_quantity': req.required_quantity,
                    'required_unit': req.required_unit,
                    'available_quantity': req.available_quantity,
                    'available_unit': req.available_unit,
                    'status': req.status,
                    'shortage': req.shortage,
                    'cost_per_unit': req.cost_per_unit,
                    'total_cost': req.total_cost,
                    'is_available': req.is_available
                }
                for req in self.ingredient_requirements
            ],
            'stock_results': [
                {
                    'ingredient_id': req.ingredient_id,
                    'ingredient_name': req.ingredient_name,
                    'needed_amount': req.required_quantity,
                    'unit': req.required_unit,
                    'available': req.is_available,
                    'available_quantity': req.available_quantity,
                    'shortage': req.shortage
                }
                for req in self.ingredient_requirements
            ],
            'all_available': all(req.is_available for req in self.ingredient_requirements),
            'container_strategy': {
                'selected_containers': [
                    {
                        'container_id': opt.container_id,
                        'container_name': opt.container_name,
                        'capacity': opt.capacity,
                        'available_quantity': opt.available_quantity,
                        'containers_needed': opt.containers_needed,
                        'cost_each': opt.cost_each
                    }
                    for opt in self.container_strategy.selected_containers
                ] if self.container_strategy else [],
                'total_capacity': self.container_strategy.total_capacity if self.container_strategy else 0,
                'containment_percentage': self.container_strategy.containment_percentage if self.container_strategy else 0,
                'is_complete': self.container_strategy.is_complete if self.container_strategy else False,
                'warnings': self.container_strategy.warnings if self.container_strategy else []
            } if self.container_strategy else None,
            'all_container_options': [
                {
                    'container_id': opt.container_id,
                    'container_name': opt.container_name,
                    'capacity': opt.capacity,
                    'available_quantity': opt.available_quantity,
                    'containers_needed': opt.containers_needed,
                    'cost_each': opt.cost_each,
                    'fill_percentage': opt.fill_percentage,
                    'total_capacity': opt.total_capacity
                }
                for opt in self.container_options
            ],
            'cost_breakdown': self.cost_breakdown.to_dict() if self.cost_breakdown else None,
            'issues': self.issues,
            'status': self.status.value
        }
