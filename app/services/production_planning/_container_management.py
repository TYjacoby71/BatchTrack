
"""
Container Management for Production Planning

Clean, maintainable container selection using a greedy algorithm approach.
Replaces the complex recursive bin-packing with an intuitive, efficient solution.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from ...models import Recipe, InventoryItem, IngredientCategory
from flask_login import current_user
from .types import ContainerStrategy, ContainerOption, ContainerFillStrategy

logger = logging.getLogger(__name__)

# --- Data Structures for Clarity ---

@dataclass
class ContainerOptionData:
    """A structured class to hold all data about a potential container."""
    id: int
    name: str
    available_qty: int
    original_capacity: float
    original_unit: str
    converted_capacity: float
    is_conversion_successful: bool

@dataclass
class FillStrategy:
    """The final result of the planning, detailing which containers to use."""
    containers_to_use: Dict[int, int]  # {container_id: quantity_to_use}
    total_capacity: float
    efficiency: float
    warnings: List[str]

# --- Main Service Class ---

class ContainerPlanner:
    """
    Encapsulates all logic for finding the optimal container strategy for a recipe.
    """
    def __init__(self, recipe: Recipe, scale: float):
        self.recipe = recipe
        self.scale = scale
        self.organization_id = current_user.organization_id if current_user.is_authenticated else None
        self.total_yield = (recipe.predicted_yield or 0) * self.scale
        self.yield_unit = recipe.predicted_yield_unit or 'ml'
        self.options: List[ContainerOptionData] = []

    def find_best_strategy(self) -> Optional[FillStrategy]:
        """
        Main entry point to find the best container fill strategy.
        """
        if self.total_yield <= 0:
            logger.warning(f"No yield for recipe {self.recipe.id}, cannot plan containers.")
            return None

        self._fetch_and_process_options()

        if not self.options:
            logger.warning(f"No valid container options found for recipe {self.recipe.id}.")
            return None

        return self._create_greedy_fill_strategy()

    def _fetch_and_process_options(self):
        """
        Fetches allowed containers from DB, processes them, and populates self.options.
        This combines the old _get_allowed_containers and _process_container_capacities.
        """
        # 1. Get allowed container IDs from the recipe, with a fallback
        container_ids = self._get_allowed_container_ids()
        if not container_ids:
            return

        # 2. Fetch all container DB objects in a single query (N+1 safe)
        containers_from_db = InventoryItem.query.filter(
            InventoryItem.id.in_(container_ids),
            InventoryItem.organization_id == self.organization_id,
            InventoryItem.quantity > 0  # Only fetch containers with stock
        ).all()

        # 3. Process each container, converting units and creating ContainerOption objects
        processed_options = []
        for container in containers_from_db:
            storage_capacity = getattr(container, 'storage_amount', None)
            storage_unit = getattr(container, 'storage_unit', None)

            if not storage_capacity or not storage_unit:
                logger.warning(f"⚠️  CONTAINER SKIPPED: {container.name} - missing capacity or unit")
                continue

            converted_capacity, success = self._convert_capacity(storage_capacity, storage_unit)
            
            # Only include containers with successful conversions
            if not success or converted_capacity <= 0:
                logger.warning(f"⚠️  CONTAINER FILTERED: {container.name} - conversion failed or zero capacity")
                continue
            
            processed_options.append(
                ContainerOptionData(
                    id=container.id,
                    name=container.name,
                    available_qty=int(container.quantity or 0),
                    original_capacity=storage_capacity,
                    original_unit=storage_unit,
                    converted_capacity=round(converted_capacity, 3),
                    is_conversion_successful=success
                )
            )
            logger.info(f"✅ CONTAINER INCLUDED: {container.name} - {converted_capacity} {self.yield_unit}")
        
        # Sort options by largest converted capacity first for the greedy algorithm
        self.options = sorted(processed_options, key=lambda o: o.converted_capacity, reverse=True)

    def _get_allowed_container_ids(self) -> List[int]:
        """Gets container IDs from the recipe, falling back to all org containers if none are specified."""
        allowed_ids = getattr(self.recipe, 'container_ids', [])
        if allowed_ids:
            logger.info(f"Using recipe-defined containers for recipe {self.recipe.id}: {allowed_ids}")
            return allowed_ids

        # Fallback logic
        logger.warning(f"Recipe {self.recipe.id} has no allowed containers. Falling back to all org containers.")
        container_category = IngredientCategory.query.filter_by(name='Container', organization_id=self.organization_id).first()
        if not container_category:
            return []
        
        all_org_containers = InventoryItem.query.filter_by(
            organization_id=self.organization_id,
            category_id=container_category.id
        ).with_entities(InventoryItem.id).all()

        return [c_id for c_id, in all_org_containers]

    def _convert_capacity(self, capacity: float, unit: str) -> Tuple[float, bool]:
        """Converts a container's capacity to the recipe's yield unit."""
        if unit == self.yield_unit:
            return capacity, True
        
        try:
            from ...services.unit_conversion import ConversionEngine
            result = ConversionEngine.convert_units(capacity, unit, self.yield_unit)
            
            converted_value = result['converted_value'] if isinstance(result, dict) else float(result)
            logger.info(f"✅ CONVERSION: {capacity} {unit} -> {converted_value} {self.yield_unit}")
            return converted_value, True
        except Exception as e:
            logger.warning(f"❌ CONVERSION FAILED: Cannot convert {capacity} {unit} to {self.yield_unit}: {e}")
            return 0.0, False  # Return 0 capacity for failed conversions

    def _create_greedy_fill_strategy(self) -> FillStrategy:
        """
        Uses a greedy algorithm to find the most efficient combination of containers.
        This replaces the complex recursive bin-packing.
        """
        containers_to_use = {}
        remaining_yield = self.total_yield
        
        # Iterate through available containers, from largest to smallest
        for option in self.options:
            if remaining_yield <= 0:
                break
            
            # How many of this container can we use?
            num_to_use = min(
                option.available_qty,
                math.floor(remaining_yield / option.converted_capacity)
            )

            if num_to_use > 0:
                containers_to_use[option.id] = num_to_use
                remaining_yield -= num_to_use * option.converted_capacity

        # If there's still a small amount left, try to fill it with the smallest container
        if remaining_yield > 0 and self.options:
            smallest_option = self.options[-1]  # Last one is smallest
            if (smallest_option.converted_capacity >= remaining_yield and 
                smallest_option.available_qty > containers_to_use.get(smallest_option.id, 0)):
                containers_to_use[smallest_option.id] = containers_to_use.get(smallest_option.id, 0) + 1

        # Calculate final metrics
        total_capacity = sum(
            next(o.converted_capacity for o in self.options if o.id == cid) * qty
            for cid, qty in containers_to_use.items()
        )
        efficiency = (self.total_yield / total_capacity) * 100 if total_capacity > 0 else 0
        
        warnings = []
        if not containers_to_use:
            warnings.append("No suitable containers found. Check that containers have compatible units that can be converted to the recipe's yield unit.")
            if self.options:
                available_units = list(set(opt.original_unit for opt in self.options))
                warnings.append(f"Available container units: {', '.join(available_units)}. Recipe yield unit: {self.yield_unit}")
        elif efficiency < 90 and efficiency > 0:
            warnings.append(f"Low fill efficiency: {efficiency:.1f}%. Consider different container sizes.")

        return FillStrategy(
            containers_to_use=containers_to_use,
            total_capacity=total_capacity,
            efficiency=efficiency,
            warnings=warnings
        )

# --- Legacy Interface Functions ---

def analyze_container_options(recipe: Recipe, scale: float, preferred_container_id: Optional[int] = None, organization_id: Optional[int] = None) -> Tuple[Optional[ContainerStrategy], List[Dict[str, Any]]]:
    """
    Legacy interface that uses the new ContainerPlanner internally.
    Returns the old format for compatibility.
    """
    try:
        planner = ContainerPlanner(recipe, scale)
        strategy = planner.find_best_strategy()

        if not strategy or not strategy.containers_to_use:
            return None, []
        
        # Convert to legacy ContainerStrategy format
        selected_containers = []
        container_options = []
        
        for option in planner.options:
            containers_needed = strategy.containers_to_use.get(option.id, 0)
            
            # Add to options list
            container_options.append({
                'container_id': option.id,
                'container_name': option.name,
                'capacity': option.converted_capacity,
                'available_quantity': option.available_qty,
                'containers_needed': containers_needed,
                'cost_each': 0.0  # Cost calculation handled elsewhere
            })
            
            # Add to selected if used
            if containers_needed > 0:
                selected_containers.append(ContainerOption(
                    container_id=option.id,
                    container_name=option.name,
                    capacity=option.converted_capacity,
                    available_quantity=option.available_qty,
                    containers_needed=containers_needed,
                    cost_each=0.0
                ))

        container_strategy = ContainerStrategy(
            selected_containers=selected_containers,
            total_capacity=strategy.total_capacity,
            containment_percentage=min(100.0, strategy.efficiency),
            fill_strategy=ContainerFillStrategy(
                selected_containers=[],
                total_capacity=strategy.total_capacity,
                containment_percentage=min(100.0, strategy.efficiency),
                strategy_type="greedy_optimized"
            ),
            warnings=strategy.warnings
        )

        return container_strategy, container_options

    except Exception as e:
        logger.error(f"Error in analyze_container_options: {e}")
        return None, []

def get_container_plan_for_api(recipe_id: int, scale: float) -> Dict[str, Any]:
    """
    API wrapper that uses the ContainerPlanner and formats a JSON response.
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        planner = ContainerPlanner(recipe, scale)
        strategy = planner.find_best_strategy()

        if not strategy or not strategy.containers_to_use:
            return {
                'success': False, 
                'error': 'No suitable container combination found.',
                'available_options': [],
                'required_yield': planner.total_yield
            }
        
        # Format the selection for the frontend
        container_selection = []
        for option in planner.options:
            if option.id in strategy.containers_to_use:
                container_selection.append({
                    'id': option.id,
                    'name': option.name,
                    'quantity': strategy.containers_to_use[option.id],
                    'available_quantity': option.available_qty,
                    'capacity': option.original_capacity,  # Original
                    'unit': option.original_unit,
                    'capacity_in_yield_unit': option.converted_capacity,  # Converted
                    'yield_unit': planner.yield_unit,
                    'conversion_successful': option.is_conversion_successful,
                    'containers_needed': strategy.containers_to_use[option.id],
                    'total_yield_needed': planner.total_yield
                })

        return {
            'success': True,
            'container_selection': container_selection,
            'total_capacity': strategy.total_capacity,
            'containment_percentage': min(100.0, strategy.efficiency),
            'warnings': strategy.warnings
        }

    except Exception as e:
        logger.error(f"Error in get_container_plan_for_api for recipe {recipe_id}: {e}")
        return {'success': False, 'error': 'An unexpected error occurred during container planning.'}
