"""
Container Management for Production Planning

Handles container selection, optimization, and fill strategies for production batches.
"""

import logging
from typing import Dict, List, Any, Optional
from ...models import Recipe, InventoryItem
from flask_login import current_user
from ..stock_check import UniversalStockCheckService
from ..stock_check.types import StockCheckRequest, InventoryCategory
from .types import ContainerOption, ContainerStrategy, ContainerFillStrategy


logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe,
    scale: float,
    preferred_container_id: Optional[int],
    organization_id: int
) -> Tuple[Optional[ContainerStrategy], List[ContainerOption]]:
    """
    Analyze all container options for a recipe and recommend the best strategy.

    Returns (selected_strategy, all_options)
    """
    try:
        logger.info(f"CONTAINER_ANALYSIS: Analyzing containers for recipe {recipe.id}")

        # Get available containers
        container_options = _get_available_containers(recipe, organization_id)

        if not container_options:
            logger.warning(f"No containers available for recipe {recipe.id}")
            return None, []

        # Calculate fill requirements
        yield_amount = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'ml'

        # Analyze each container option
        analyzed_options = []
        for container in container_options:
            option = _analyze_container_option(container, yield_amount, yield_unit)
            if option:
                analyzed_options.append(option)

        if not analyzed_options:
            logger.warning("No suitable container options found after analysis")
            return None, container_options

        # Select best strategy
        if preferred_container_id:
            strategy = _create_user_specified_strategy(analyzed_options, preferred_container_id)
        else:
            strategy = _select_optimal_strategy(analyzed_options)

        logger.info(f"CONTAINER_ANALYSIS: Selected strategy {strategy.strategy_type.value}")
        return strategy, analyzed_options

    except Exception as e:
        logger.error(f"Error analyzing container options: {e}")
        return None, []


def _get_available_containers(recipe: Recipe, organization_id: int) -> List[InventoryItem]:
    """Get containers available for this recipe"""
    try:
        # Check if recipe has specific allowed containers
        if hasattr(recipe, 'allowed_containers') and recipe.allowed_containers:
            containers = InventoryItem.query.filter(
                InventoryItem.id.in_(recipe.allowed_containers),
                InventoryItem.type == 'container',
                InventoryItem.organization_id == organization_id
            ).all()
        else:
            # Get all available containers for this organization
            containers = InventoryItem.query.filter_by(
                type='container',
                organization_id=organization_id
            ).all()

        # Filter to only containers with stock
        available_containers = [c for c in containers if hasattr(c, 'quantity') and (c.quantity or 0) > 0]

        logger.info(f"Found {len(available_containers)} available containers")
        return available_containers

    except Exception as e:
        logger.error(f"Error getting available containers: {e}")
        return []


def _analyze_container_option(container: InventoryItem, yield_amount: float, yield_unit: str) -> Optional[ContainerOption]:
    """Analyze a single container option"""
    try:
        # Get container capacity
        storage_capacity = getattr(container, 'storage_amount', 0) or 0
        storage_unit = getattr(container, 'storage_unit', 'ml') or 'ml'

        if storage_capacity <= 0:
            return None

        # Calculate how many containers needed (simplified - assumes compatible units)
        containers_needed = max(1, int((yield_amount + storage_capacity - 1) // storage_capacity))  # Ceiling division

        # Calculate fill percentage
        total_capacity = storage_capacity * containers_needed
        fill_percentage = (yield_amount / total_capacity * 100) if total_capacity > 0 else 0

        # Available quantity
        available_quantity = getattr(container, 'quantity', 0) or 0
        cost_each = getattr(container, 'cost_per_unit', 0) or 0

        return ContainerOption(
            container_id=container.id,
            container_name=container.name,
            storage_capacity=storage_capacity,
            storage_unit=storage_unit,
            available_quantity=available_quantity,
            cost_each=cost_each,
            fill_percentage=fill_percentage,
            containers_needed=containers_needed
        )

    except Exception as e:
        logger.error(f"Error analyzing container {container.id}: {e}")
        return None


def _select_optimal_strategy(options: List[ContainerOption]) -> ContainerStrategy:
    """Select the optimal container strategy from available options"""

    # Sort by efficiency (fill percentage) and then by total cost
    viable_options = [opt for opt in options if opt.available_quantity >= opt.containers_needed]

    if not viable_options:
        # No perfect options, find best available
        viable_options = sorted(options, key=lambda x: (x.available_quantity, -x.fill_percentage))
        viable_options = viable_options[:1] if viable_options else []

    if not viable_options:
        raise ValueError("No viable container options")

    # Select strategy based on options
    if len(viable_options) == 1:
        selected = viable_options[0]
        strategy_type = ContainerFillStrategy.SINGLE_LARGE
    else:
        # Select highest efficiency option
        selected = max(viable_options, key=lambda x: x.fill_percentage)
        strategy_type = ContainerFillStrategy.SINGLE_LARGE

    total_cost = selected.cost_each * selected.containers_needed
    waste_percentage = max(0, 100 - selected.fill_percentage)

    return ContainerStrategy(
        strategy_type=strategy_type,
        selected_containers=[selected],
        total_containers_needed=selected.containers_needed,
        total_container_cost=total_cost,
        average_fill_percentage=selected.fill_percentage,
        waste_percentage=waste_percentage
    )


def _create_user_specified_strategy(options: List[ContainerOption], container_id: int) -> Optional[ContainerStrategy]:
    """Create strategy for user-specified container"""

    selected_option = next((opt for opt in options if opt.container_id == container_id), None)

    if not selected_option:
        # Fall back to optimal strategy
        return _select_optimal_strategy(options)

    total_cost = selected_option.cost_each * selected_option.containers_needed
    waste_percentage = max(0, 100 - selected_option.fill_percentage)

    return ContainerStrategy(
        strategy_type=ContainerFillStrategy.USER_SPECIFIED,
        selected_containers=[selected_option],
        total_containers_needed=selected_option.containers_needed,
        total_container_cost=total_cost,
        average_fill_percentage=selected.fill_percentage,
        waste_percentage=waste_percentage
    )


def select_optimal_containers(recipe_id: int, scale: float = 1.0) -> dict:
    """Legacy compatibility function for container selection"""
    try:
        from ...models import Recipe
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        organization_id = current_user.organization_id if current_user.is_authenticated else None
        strategy, options = analyze_container_options(recipe, scale, None, organization_id)

        return {
            'success': True,
            'strategy': strategy.strategy_type.value if strategy else None,
            'selected_containers': [opt.__dict__ for opt in (strategy.selected_containers if strategy else [])],
            'all_options': [opt.__dict__ for opt in options]
        }

    except Exception as e:
        logger.error(f"Error selecting optimal containers: {e}")
        return {'success': False, 'error': str(e)}


def calculate_container_fill_strategy(recipe_id: int, scale: float, yield_amount: float, yield_unit: str) -> Dict[str, Any]:
    """
    Calculate optimal container selection for given yield.
    This contains the business logic that was previously in the template.
    """
    try:
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        # Get available containers for this recipe
        if recipe.allowed_containers:
            containers = InventoryItem.query.filter(
                InventoryItem.id.in_(recipe.allowed_containers),
                InventoryItem.type == 'container',
                InventoryItem.organization_id == current_user.organization_id
            ).all()
        else:
            containers = InventoryItem.query.filter_by(
                type='container',
                organization_id=current_user.organization_id
            ).all()

        # Filter to containers with stock and sort by capacity (largest first)
        available_containers = [
            {
                'id': c.id,
                'name': c.name,
                'capacity': c.storage_capacity or 0,
                'stock_qty': c.quantity or 0,
                'unit': c.storage_unit or 'ml'
            }
            for c in containers if (c.quantity or 0) > 0
        ]
        available_containers.sort(key=lambda x: x['capacity'], reverse=True)

        # Execute auto-fill algorithm
        remaining_volume = yield_amount
        selected_containers = []

        # First pass: Fill with largest containers
        for container in available_containers:
            if remaining_volume <= 0:
                break

            capacity = container['capacity']
            if capacity <= 0:
                continue

            max_needed = int(remaining_volume // capacity)
            qty_to_use = min(max_needed, container['stock_qty'])

            if qty_to_use > 0:
                selected_containers.append({
                    'id': container['id'],
                    'name': container['name'],
                    'capacity': capacity,
                    'quantity': qty_to_use,
                    'unit': container['unit']
                })
                remaining_volume -= qty_to_use * capacity

        # Second pass: Add one more container for partial fill if needed
        if remaining_volume > 0:
            for container in available_containers:
                already_used = next((s for s in selected_containers if s['id'] == container['id']), None)
                remaining_stock = container['stock_qty'] - (already_used['quantity'] if already_used else 0)

                if remaining_stock > 0:
                    if already_used:
                        already_used['quantity'] += 1
                    else:
                        selected_containers.append({
                            'id': container['id'],
                            'name': container['name'],
                            'capacity': container['capacity'],
                            'quantity': 1,
                            'unit': container['unit']
                        })
                    break

        return {
            'success': True,
            'container_selection': selected_containers,
            'total_capacity': sum(s['capacity'] * s['quantity'] for s in selected_containers),
            'containment_percentage': min(100, (sum(s['capacity'] * s['quantity'] for s in selected_containers) / yield_amount) * 100) if yield_amount > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error calculating container fill strategy: {e}")
        return {'success': False, 'error': str(e)}