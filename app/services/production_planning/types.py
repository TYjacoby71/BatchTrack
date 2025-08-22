
"""
Production Planning Types

Defines the data structures used throughout the production planning process.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class ProductionStatus(Enum):
    FEASIBLE = "feasible"
    INSUFFICIENT_INGREDIENTS = "insufficient_ingredients"
    NO_CONTAINERS = "no_containers"
    COST_PROHIBITIVE = "cost_prohibitive"


class ContainerFillStrategy(Enum):
    SINGLE_LARGE = "single_large"  # Use one large container
    MULTIPLE_SMALL = "multiple_small"  # Use multiple smaller containers
    MIXED_SIZES = "mixed_sizes"  # Optimal mix of sizes
    USER_SPECIFIED = "user_specified"  # User chose specific container


@dataclass
class ProductionRequest:
    """Request for production planning analysis"""
    recipe_id: int
    scale: float = 1.0
    preferred_container_id: Optional[int] = None
    include_container_analysis: bool = True
    max_cost_per_unit: Optional[float] = None
    organization_id: Optional[int] = None


@dataclass
class IngredientRequirement:
    """Individual ingredient requirement"""
    ingredient_id: int
    ingredient_name: str
    base_quantity: float
    scaled_quantity: float
    unit: str
    available_quantity: float
    cost_per_unit: float
    total_cost: float
    status: str  # 'available', 'low', 'insufficient'


@dataclass
class ContainerOption:
    """Available container option"""
    container_id: int
    container_name: str
    storage_capacity: float
    storage_unit: str
    available_quantity: int
    cost_each: float
    fill_percentage: float  # How full this container would be
    containers_needed: int


@dataclass
class ContainerStrategy:
    """Container selection strategy result"""
    strategy_type: ContainerFillStrategy
    selected_containers: List[ContainerOption]
    total_containers_needed: int
    total_container_cost: float
    average_fill_percentage: float
    waste_percentage: float


@dataclass
class CostBreakdown:
    """Detailed cost analysis"""
    ingredient_costs: List[Dict[str, Any]]
    container_costs: List[Dict[str, Any]] 
    total_ingredient_cost: float
    total_container_cost: float
    total_production_cost: float
    cost_per_unit: float
    yield_amount: float
    yield_unit: str


@dataclass
class ProductionPlan:
    """Complete production plan result"""
    request: ProductionRequest
    status: ProductionStatus
    feasible: bool
    
    # Requirements
    ingredient_requirements: List[IngredientRequirement]
    projected_yield: Dict[str, Any]
    
    # Container analysis
    container_strategy: Optional[ContainerStrategy]
    container_options: List[ContainerOption]
    
    # Cost analysis
    cost_breakdown: CostBreakdown
    
    # Issues and recommendations
    issues: List[str]
    recommendations: List[str]
    
    # Batch preparation data
    batch_ready_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'success': self.feasible,
            'status': self.status.value,
            'feasible': self.feasible,
            'recipe_id': self.request.recipe_id,
            'scale': self.request.scale,
            'ingredient_requirements': [
                {
                    'item_id': req.ingredient_id,
                    'item_name': req.ingredient_name,
                    'needed_quantity': req.scaled_quantity,
                    'available_quantity': req.available_quantity,
                    'unit': req.unit,
                    'status': req.status,
                    'cost_per_unit': req.cost_per_unit,
                    'total_cost': req.total_cost,
                    'category': 'ingredient'
                }
                for req in self.ingredient_requirements
            ],
            'container_strategy': {
                'strategy': self.container_strategy.strategy_type.value if self.container_strategy else None,
                'containers': [
                    {
                        'item_id': opt.container_id,
                        'item_name': opt.container_name,
                        'storage_capacity': opt.storage_capacity,
                        'storage_unit': opt.storage_unit,
                        'available': opt.available_quantity,
                        'needed': opt.containers_needed,
                        'cost_each': opt.cost_each,
                        'fill_percentage': opt.fill_percentage,
                        'category': 'container'
                    }
                    for opt in (self.container_strategy.selected_containers if self.container_strategy else [])
                ]
            } if self.container_strategy else None,
            'cost_info': {
                'total_cost': self.cost_breakdown.total_production_cost,
                'cost_per_unit': self.cost_breakdown.cost_per_unit,
                'ingredient_cost': self.cost_breakdown.total_ingredient_cost,
                'container_cost': self.cost_breakdown.total_container_cost,
                'yield_amount': self.cost_breakdown.yield_amount,
                'yield_unit': self.cost_breakdown.yield_unit
            },
            'issues': self.issues,
            'recommendations': self.recommendations,
            'all_available': self.status not in [ProductionStatus.INSUFFICIENT_INGREDIENTS, ProductionStatus.NO_CONTAINERS],
            'all_ok': self.feasible  # Legacy compatibility
        }
