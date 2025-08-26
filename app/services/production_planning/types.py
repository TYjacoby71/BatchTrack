"""
Production Planning Types

Defines the data structures used throughout the production planning process.
"""

from dataclasses import dataclass, field
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

    # Placeholder attributes for frontend compatibility
    item_id: int = field(init=False, repr=False)
    item_name: str = field(init=False, repr=False)
    needed_quantity: float = field(init=False, repr=False)
    needed_unit: str = field(init=False, repr=False)
    available_unit: str = field(init=False, repr=False)
    formatted_needed: str = field(init=False, repr=False)
    formatted_available: str = field(init=False, repr=False)

    def __post_init__(self):
        # Initialize placeholder attributes
        self.item_id = self.ingredient_id
        self.item_name = self.ingredient_name
        self.needed_quantity = self.scaled_quantity
        self.needed_unit = self.unit
        self.available_unit = self.unit # Assuming same unit for availability
        self.formatted_needed = f"{self.scaled_quantity} {self.unit}"
        self.formatted_available = f"{self.available_quantity} {self.unit}"


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

    # Placeholder attributes for frontend compatibility
    name: str = field(init=False, repr=False)
    quantity: int = field(init=False, repr=False)
    capacity: float = field(init=False, repr=False)
    stock_qty: int = field(init=False, repr=False)


    def __post_init__(self):
        # Initialize placeholder attributes
        self.name = self.container_name
        self.quantity = self.containers_needed
        self.capacity = self.storage_capacity
        self.stock_qty = self.available_quantity


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
    """Complete production plan with all analysis results"""
    request: ProductionRequest
    status: ProductionStatus
    feasible: bool
    ingredient_requirements: List[IngredientRequirement]
    projected_yield: Dict[str, Any]
    container_strategy: Optional[ContainerStrategy] = None
    container_options: List[ContainerOption] = field(default_factory=list)
    cost_breakdown: Optional[CostBreakdown] = None
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert production plan to dictionary for API responses"""
        ingredient_list = []
        if self.ingredient_requirements:
            for req in self.ingredient_requirements:
                ingredient_list.append({
                    'item_id': req.item_id,
                    'item_name': req.item_name,
                    'ingredient_name': req.item_name,  # For backwards compatibility
                    'needed_quantity': req.needed_quantity,
                    'needed_amount': req.needed_quantity,  # For backwards compatibility
                    'quantity_needed': req.needed_quantity,  # Alternative format
                    'needed_unit': req.needed_unit,
                    'unit': req.needed_unit,  # For backwards compatibility
                    'available_quantity': req.available_quantity,
                    'available_unit': req.available_unit,
                    'status': req.status,
                    'is_available': req.status not in ['insufficient', 'unavailable', 'NEEDED', 'OUT_OF_STOCK'],
                    'formatted_needed': req.formatted_needed if hasattr(req, 'formatted_needed') else f"{req.needed_quantity} {req.needed_unit}",
                    'formatted_available': req.formatted_available if hasattr(req, 'formatted_available') else f"{req.available_quantity} {req.available_unit}",
                    'category': 'ingredient'
                })

        container_list = []
        if self.container_strategy and hasattr(self.container_strategy, 'selected_containers') and self.container_strategy.selected_containers:
            for container in self.container_strategy.selected_containers:
                container_list.append({
                    'item_id': container.get('container_id'),
                    'item_name': container.get('name', ''),
                    'quantity_needed': container.get('quantity', 0),
                    'available_quantity': container.get('stock_qty', 0),
                    'capacity': container.get('capacity', 0),
                    'category': 'container'
                })

        # Determine if all ingredients are available
        all_ingredients_available = all(
            req.status not in ['insufficient', 'unavailable', 'NEEDED', 'OUT_OF_STOCK']
            for req in (self.ingredient_requirements or [])
        )

        return {
            'success': True,
            'feasible': self.feasible,
            'status': self.status.value,
            'all_available': all_ingredients_available,
            'stock_results': ingredient_list + container_list,
            'ingredient_requirements': ingredient_list,
            'container_options': container_list,
            'projected_yield': self.projected_yield,
            'cost_breakdown': self.cost_breakdown.to_dict() if self.cost_breakdown and hasattr(self.cost_breakdown, 'to_dict') else {},
            'issues': self.issues,
            'recommendations': self.recommendations
        }