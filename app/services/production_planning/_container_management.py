"""
Container Management for Production Planning

Clean, direct container selection using a greedy algorithm.
No legacy compatibility layers.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from ...models import Recipe, InventoryItem, IngredientCategory
from flask_login import current_user
from .types import ContainerStrategy, ContainerOption

logger = logging.getLogger(__name__)

@dataclass
class ContainerCandidate:
    """A container option with conversion data"""
    id: int
    name: str
    available_qty: int
    capacity_in_recipe_units: float
    original_capacity: float
    original_unit: str

class ContainerPlanner:
    """Container strategy planning for recipes"""

    def __init__(self, recipe: Recipe, scale: float):
        self.recipe = recipe
        self.scale = scale
        self.organization_id = current_user.organization_id if current_user.is_authenticated else None
        self.total_yield = (recipe.predicted_yield or 0) * self.scale
        self.yield_unit = recipe.predicted_yield_unit or 'ml'
        self.candidates: List[ContainerCandidate] = []

    def plan_containers(self) -> Optional[ContainerStrategy]:
        """Main entry point for container planning"""
        if self.total_yield <= 0:
            raise ValueError(f"Recipe '{self.recipe.name}' has no predicted yield configured.")

        self._load_container_candidates()

        if not self.candidates:
            raise ValueError(f"No suitable containers found for recipe '{self.recipe.name}'. Check that containers have compatible units and sufficient stock.")

        return self._create_container_strategy()

    def _load_container_candidates(self):
        """Load and process container candidates"""
        container_ids = self._get_allowed_container_ids()

        containers_from_db = InventoryItem.query.filter(
            InventoryItem.id.in_(container_ids),
            InventoryItem.organization_id == self.organization_id,
            InventoryItem.quantity > 0
        ).all()

        for container in containers_from_db:
            storage_capacity = getattr(container, 'storage_amount', None)
            storage_unit = getattr(container, 'storage_unit', None)

            if not storage_capacity or not storage_unit:
                logger.warning(f"Container {container.name} missing capacity data - skipped")
                continue

            converted_capacity = self._convert_capacity(storage_capacity, storage_unit)
            if converted_capacity <= 0:
                logger.warning(f"Container {container.name} conversion failed - skipped")
                continue

            self.candidates.append(ContainerCandidate(
                id=container.id,
                name=container.name,
                available_qty=int(container.quantity or 0),
                capacity_in_recipe_units=converted_capacity,
                original_capacity=storage_capacity,
                original_unit=storage_unit
            ))

        # Sort largest first for greedy algorithm
        self.candidates.sort(key=lambda c: c.capacity_in_recipe_units, reverse=True)

    def _get_allowed_container_ids(self) -> List[int]:
        """Gets container IDs from the recipe. Raises error if none are configured."""
        allowed_ids = getattr(self.recipe, 'container_ids', [])
        if allowed_ids:
            logger.info(f"Using recipe-defined containers for recipe {self.recipe.id}: {allowed_ids}")
            return allowed_ids

        # No fallback - this is a configuration error that should be fixed
        raise ValueError(f"Recipe '{self.recipe.name}' (ID: {self.recipe.id}) has no containers configured. Please edit the recipe and select appropriate containers before running production planning.")

    def _convert_capacity(self, capacity: float, unit: str) -> float:
        """Convert container capacity to recipe yield units"""
        if unit == self.yield_unit:
            return capacity

        try:
            from ...services.unit_conversion import ConversionEngine
            result = ConversionEngine.convert_units(capacity, unit, self.yield_unit)
            converted_value = result['converted_value'] if isinstance(result, dict) else float(result)
            return converted_value
        except Exception as e:
            logger.warning(f"Cannot convert {capacity} {unit} to {self.yield_unit}: {e}")
            return 0.0

    def _create_container_strategy(self) -> ContainerStrategy:
        """Create container strategy using greedy selection"""
        selected_containers = []
        remaining_yield = self.total_yield

        for candidate in self.candidates:
            if remaining_yield <= 0:
                break

            containers_needed = min(
                candidate.available_qty,
                math.ceil(remaining_yield / candidate.capacity_in_recipe_units)
            )

            if containers_needed > 0:
                selected_containers.append(ContainerOption(
                    container_id=candidate.id,
                    container_name=candidate.name,
                    capacity=candidate.capacity_in_recipe_units,
                    available_quantity=candidate.available_qty,
                    containers_needed=containers_needed,
                    cost_each=0.0  # Cost calculated elsewhere
                ))
                remaining_yield -= containers_needed * candidate.capacity_in_recipe_units

        if not selected_containers:
            raise ValueError(f"Cannot find suitable container combination for {self.total_yield} {self.yield_unit}")

        total_capacity = sum(c.capacity * c.containers_needed for c in selected_containers)
        containment_percentage = (self.total_yield / total_capacity * 100) if total_capacity > 0 else 0

        warnings = []
        if containment_percentage < 80:
            warnings.append(f"Low container utilization: {containment_percentage:.1f}%. Consider different container sizes.")

        return ContainerStrategy(
            selected_containers=selected_containers,
            total_capacity=total_capacity,
            containment_percentage=min(100.0, containment_percentage),
            warnings=warnings
        )

# Public interface - single clean function
def analyze_container_options(recipe: Recipe, scale: float, preferred_container_id: Optional[int] = None, organization_id: Optional[int] = None):
    """Analyze container options for a recipe at given scale"""
    try:
        planner = ContainerPlanner(recipe, scale)
        strategy = planner.plan_containers()

        # Convert to expected format for container options
        container_options = []
        for container in planner.candidates:
            containers_needed = 0
            for selected in strategy.selected_containers:
                if selected.container_id == container.id:
                    containers_needed = selected.containers_needed
                    break

            container_options.append({
                'container_id': container.id,
                'container_name': container.name,
                'capacity': container.capacity_in_recipe_units,
                'available_quantity': container.available_qty,
                'containers_needed': containers_needed,
                'cost_each': 0.0
            })

        return strategy, container_options

    except Exception as e:
        logger.error(f"Container planning failed for recipe {recipe.id}: {e}")
        return None, []