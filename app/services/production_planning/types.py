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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'item_id': self.ingredient_id,
            'item_name': self.ingredient_name,
            'needed_quantity': self.scaled_quantity,
            'available_quantity': self.available_quantity,
            'unit': self.unit,
            'status': self.status,
            'cost_per_unit': self.cost_per_unit,
            'total_cost': self.total_cost,
            'category': 'ingredient'
        }


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
    """Container selection strategy result"""
    strategy_type: ContainerFillStrategy
    selected_containers: List[ContainerOption]
    total_containers_needed: int
    total_container_cost: float
    average_fill_percentage: float
    waste_percentage: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'strategy': self.strategy_type.value,
            'containers': [opt.to_dict() for opt in self.selected_containers],
            'total_containers_needed': self.total_containers_needed,
            'total_container_cost': self.total_container_cost,
            'average_fill_percentage': self.average_fill_percentage,
            'waste_percentage': self.waste_percentage
        }


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
        """Convert to dictionary format for API responses"""
        # Transform ingredient requirements to stock_results format expected by frontend
        stock_results = []
        all_available = True

        for req in self.ingredient_requirements:
            req_dict = req.to_dict()
            stock_result = {
                'ingredient_id': req_dict.get('item_id'),
                'ingredient_name': req_dict.get('item_name', ''),
                'needed_amount': req_dict.get('needed_quantity', 0),
                'unit': req_dict.get('unit', ''),
                'available': req_dict.get('status') == 'available',
                'available_quantity': req_dict.get('available_quantity', 0),
                'shortage': max(0, req_dict.get('needed_quantity', 0) - req_dict.get('available_quantity', 0))
            }
            stock_results.append(stock_result)

            if req_dict.get('status') != 'available':
                all_available = False

        return {
            'success': self.feasible,
            'status': self.status.value,
            'feasible': self.feasible,
            'stock_results': stock_results,
            'all_available': all_available,
            'ingredient_requirements': [req.to_dict() for req in self.ingredient_requirements],
            'projected_yield': self.projected_yield,
            'container_strategy': self.container_strategy.to_dict() if self.container_strategy else None,
            'container_options': [opt.to_dict() for opt in self.container_options],
            'cost_breakdown': self.cost_breakdown.to_dict() if self.cost_breakdown else None,
            'issues': self.issues,
            'recommendations': self.recommendations
        }