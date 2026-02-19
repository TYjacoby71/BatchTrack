"""Production planning data types.

Synopsis:
Defines immutable plan snapshot structures shared across services.

Glossary:
- PlanSnapshot: Immutable payload stored with batch start.
- Line item: Ingredient/consumable/container data in a plan.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PortioningPlan:
    is_portioned: bool
    portion_name: Optional[str] = None
    portion_unit_id: Optional[int] = None
    portion_count: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IngredientLine:
    inventory_item_id: int
    quantity: float
    unit: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ConsumableLine:
    inventory_item_id: int
    quantity: float
    unit: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ContainerSelection:
    id: int
    quantity: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PlanSnapshot:
    recipe_id: int
    target_version_id: Optional[int]
    lineage_snapshot: Optional[str]
    scale: float
    batch_type: str
    notes: str
    projected_yield: float
    projected_yield_unit: str
    portioning: PortioningPlan
    ingredients_plan: List[IngredientLine]
    consumables_plan: List[ConsumableLine]
    containers: List[ContainerSelection]
    requires_containers: bool = False
    category_extension: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "recipe_id": self.recipe_id,
            "target_version_id": self.target_version_id,
            "lineage_snapshot": self.lineage_snapshot,
            "scale": self.scale,
            "batch_type": self.batch_type,
            "notes": self.notes,
            "projected_yield": self.projected_yield,
            "projected_yield_unit": self.projected_yield_unit,
            "portioning": self.portioning.to_dict(),
            "ingredients_plan": [ing.to_dict() for ing in self.ingredients_plan],
            "consumables_plan": [cons.to_dict() for cons in self.consumables_plan],
            "containers": [cont.to_dict() for cont in self.containers],
            "requires_containers": self.requires_containers,
            "category_extension": self.category_extension,
        }


"""
Production Planning Types

Simplified data structures focused on orchestrating recipe -> stock -> container -> batch flow.
"""


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
    scale: float
    unit: str
    total_cost: float
    status: str
    # Additional fields needed for integration
    base_quantity: float = 0.0
    scaled_quantity: float = 0.0
    available_quantity: float = 0.0
    cost_per_unit: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "item_id": self.ingredient_id,
            "item_name": self.ingredient_name,
            "scale": self.scale,
            "unit": self.unit,
            "total_cost": self.total_cost,
            "status": self.status,
            "category": "ingredient",
            "base_quantity": self.base_quantity,
            "scaled_quantity": self.scaled_quantity,
            "available_quantity": self.available_quantity,
            "cost_per_unit": self.cost_per_unit,
        }


@dataclass
class ContainerFillStrategy:
    """Container fill strategy for production batches"""

    selected_containers: List[Dict[str, Any]] = field(default_factory=list)
    total_capacity: float = 0.0
    containment_percentage: float = 0.0
    strategy_type: str = "auto"  # auto, manual, bulk

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "selected_containers": self.selected_containers,
            "total_capacity": self.total_capacity,
            "containment_percentage": self.containment_percentage,
            "strategy_type": self.strategy_type,
        }


@dataclass
class ContainerOption:
    """Individual container option for selection"""

    container_id: int
    container_name: str
    capacity: float
    available_quantity: int
    containers_needed: int
    cost_each: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "container_id": self.container_id,
            "container_name": self.container_name,
            "capacity": self.capacity,
            "available_quantity": self.available_quantity,
            "containers_needed": self.containers_needed,
            "cost_each": self.cost_each,
            "category": "container",
        }


@dataclass
class ContainerStrategy:
    """Complete container strategy for production"""

    selected_containers: List[ContainerOption] = field(default_factory=list)
    total_capacity: float = 0.0
    containment_percentage: float = 0.0
    fill_strategy: Optional[ContainerFillStrategy] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "selected_containers": [c.__dict__ for c in self.selected_containers],
            "total_capacity": self.total_capacity,
            "containment_percentage": self.containment_percentage,
            "fill_strategy": (
                self.fill_strategy.to_dict() if self.fill_strategy else None
            ),
            "warnings": self.warnings,
        }


@dataclass
class CostBreakdown:
    """Simple cost analysis"""

    ingredient_costs: List[Dict[str, Any]] = field(default_factory=list)
    container_costs: List[Dict[str, Any]] = field(default_factory=list)
    total_ingredient_cost: float = 0.0
    total_container_cost: float = 0.0
    total_production_cost: float = 0.0
    cost_per_unit: float = 0.0
    yield_amount: float = 0.0
    yield_unit: str = "count"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_cost": self.total_production_cost,
            "cost_per_unit": self.cost_per_unit,
            "ingredient_cost": self.total_ingredient_cost,
            "container_cost": self.total_container_cost,
            "ingredient_costs": self.ingredient_costs,
            "container_costs": self.container_costs,
            "yield_amount": self.yield_amount,
            "yield_unit": self.yield_unit,
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
            "success": True,
            "feasible": self.feasible,
            "stock_results": stock_results,
            "ingredient_requirements": [
                req.to_dict() for req in self.ingredient_requirements
            ],
            "container_options": [opt.to_dict() for opt in self.container_options],
            "projected_yield": self.projected_yield,
            "cost_breakdown": (
                self.cost_breakdown.to_dict() if self.cost_breakdown else {}
            ),
            "issues": self.issues,
        }
