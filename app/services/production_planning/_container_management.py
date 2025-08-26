
"""
Container Management for Production Planning

Consolidated container selection, optimization, and fill strategies for production batches.
Handles proper unit conversion and intelligent auto-fill based on container capacity.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from ...models import Recipe, InventoryItem
from flask_login import current_user
from ..stock_check import UniversalStockCheckService
from ..stock_check.types import StockCheckRequest, InventoryCategory, StockStatus
from .types import ContainerStrategy, ContainerOption, ContainerFillStrategy

logger = logging.getLogger(__name__)

# Auto-fill efficiency tolerance (±3% for 100% containment decisions)
EFFICIENCY_TOLERANCE = 0.03

def analyze_container_options(
    recipe: Recipe,
    scale: float,
    preferred_container_id: Optional[int] = None,
    organization_id: Optional[int] = None
) -> Tuple[Optional[ContainerStrategy], List[Dict[str, Any]]]:
    """
    Analyze and rank container options for a recipe at given scale.
    
    Process:
    1. Find allowed containers for recipe
    2. Convert all capacities to recipe yield unit
    3. Rank by converted capacity (largest first)
    4. Apply intelligent auto-fill strategy
    
    Returns:
        Tuple of (container_strategy, container_options_list)
    """
    try:
        # Get yield requirements in recipe units
        total_yield = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'ml'
        
        if total_yield <= 0:
            logger.warning(f"No yield calculated for recipe {recipe.id} at scale {scale}")
            return None, []

        logger.info(f"Analyzing containers for recipe {recipe.id}: {total_yield} {yield_unit} yield")

        # Step 1: Find allowed containers for this recipe
        allowed_containers = _get_allowed_containers(recipe, organization_id)
        if not allowed_containers:
            return None, []

        # Step 2: Process and convert all container capacities
        container_options = _process_container_capacities(
            allowed_containers, yield_unit, total_yield, organization_id
        )
        
        if not container_options:
            logger.warning(f"No valid containers found for recipe {recipe.id}")
            return None, []

        # Step 3: Apply intelligent auto-fill strategy
        container_strategy = _create_auto_fill_strategy(container_options, total_yield, yield_unit)

        return container_strategy, container_options

    except Exception as e:
        logger.error(f"Error in analyze_container_options: {e}")
        return None, []


def _get_allowed_containers(recipe: Recipe, organization_id: Optional[int]) -> List[int]:
    """Get allowed container IDs for recipe with fallback to all org containers."""
    
    allowed_containers = []
    use_fallback = False
    
    # Check if recipe has allowed_containers relationship or field
    if hasattr(recipe, 'allowed_containers') and recipe.allowed_containers:
        allowed_containers = [c.id if hasattr(c, 'id') else c for c in recipe.allowed_containers]
    elif hasattr(recipe, 'container_ids') and recipe.container_ids:
        allowed_containers = recipe.container_ids
    
    if not allowed_containers:
        # FALLBACK: If no containers assigned to recipe, show all organization containers
        logger.info(f"Recipe {recipe.id} has no allowed containers - using org fallback")
        use_fallback = True
        
        org_id = organization_id or (current_user.organization_id if current_user.is_authenticated else None)
        
        # Get all containers in organization
        from ...models import IngredientCategory
        container_category = IngredientCategory.query.filter_by(
            name='Container',
            organization_id=org_id
        ).first()
        
        if container_category:
            org_containers = InventoryItem.query.filter_by(
                organization_id=org_id,
                category_id=container_category.id
            ).all()
            allowed_containers = [c.id for c in org_containers]
        
        if not allowed_containers:
            logger.warning(f"No containers found in organization {org_id}")
            return []

    fallback_msg = " (fallback)" if use_fallback else ""
    logger.info(f"Recipe {recipe.id} containers{fallback_msg}: {allowed_containers}")
    
    return allowed_containers


def _process_container_capacities(
    container_ids: List[int], 
    yield_unit: str, 
    total_yield: float, 
    organization_id: Optional[int]
) -> List[Dict[str, Any]]:
    """Process containers and convert capacities to yield unit."""
    
    org_id = organization_id or (current_user.organization_id if current_user.is_authenticated else None)
    
    # SINGLE QUERY: Get all container details at once
    containers = InventoryItem.query.filter(
        InventoryItem.id.in_(container_ids),
        InventoryItem.organization_id == org_id
    ).all()
    
    containers_by_id = {c.id: c for c in containers}
    container_options = []
    
    for container_id in container_ids:
        try:
            container = containers_by_id.get(container_id)
            if not container:
                logger.warning(f"Container {container_id} not found")
                continue

            # REQUIRE proper storage capacity
            storage_capacity = getattr(container, 'storage_amount', None)
            storage_unit = getattr(container, 'storage_unit', None)
            
            if not storage_capacity or not storage_unit:
                logger.warning(f"Container {container.name} has no storage capacity - skipping")
                continue

            # Check stock availability
            available_qty = container.quantity or 0
            if available_qty <= 0:
                logger.warning(f"Container {container.name} has no stock - skipping")
                continue

            # Convert storage capacity to recipe yield unit
            capacity_in_yield_unit = storage_capacity
            conversion_successful = False
            
            if storage_unit != yield_unit:
                try:
                    from ...services.unit_conversion import ConversionEngine
                    conversion_result = ConversionEngine.convert_units(
                        storage_capacity,
                        storage_unit,
                        yield_unit,
                        ingredient_id=None
                    )
                    
                    if isinstance(conversion_result, dict):
                        capacity_in_yield_unit = conversion_result['converted_value']
                        conversion_successful = True
                        logger.info(f"Converted {container.name}: {storage_capacity} {storage_unit} → {capacity_in_yield_unit} {yield_unit}")
                    else:
                        capacity_in_yield_unit = float(conversion_result)
                        conversion_successful = True
                        
                except Exception as e:
                    logger.warning(f"Unit conversion failed for {container.name}: {e}")
                    capacity_in_yield_unit = storage_capacity
                    conversion_successful = False
            else:
                conversion_successful = True

            # Calculate containers needed based on converted capacity
            containers_needed = 1
            if capacity_in_yield_unit > 0:
                containers_needed = max(1, int(math.ceil(total_yield / capacity_in_yield_unit)))

            container_option = {
                'id': container_id,
                'name': container.name,
                'capacity': storage_capacity,  # Original capacity
                'unit': storage_unit,  # Original unit
                'capacity_in_yield_unit': round(capacity_in_yield_unit, 3),  # Converted capacity
                'yield_unit': yield_unit,
                'conversion_successful': conversion_successful,
                'available_quantity': int(available_qty),
                'containers_needed': containers_needed,
                'total_capacity_yield_units': capacity_in_yield_unit * containers_needed,
                'fill_percentage': min(100.0, (total_yield / (capacity_in_yield_unit * containers_needed)) * 100) if capacity_in_yield_unit > 0 else 0
            }

            container_options.append(container_option)
            logger.info(f"Processed {container.name}: {capacity_in_yield_unit} {yield_unit} capacity, need {containers_needed}")

        except Exception as e:
            logger.error(f"Error processing container {container_id}: {e}")
            continue

    # Sort by converted capacity (largest first) for intelligent auto-fill
    container_options.sort(key=lambda x: x['capacity_in_yield_unit'], reverse=True)
    
    return container_options


def _create_auto_fill_strategy(
    container_options: List[Dict[str, Any]], 
    total_yield: float, 
    yield_unit: str
) -> Optional[ContainerStrategy]:
    """
    Create intelligent auto-fill strategy selecting optimal containers.
    
    Strategy:
    1. Try largest container that has sufficient stock
    2. Check if fill percentage is reasonable (±3% tolerance for 100%)
    3. If overfilled by more than tolerance, try smaller containers
    4. Select container with best fill efficiency
    """
    
    if not container_options:
        return None

    best_option = None
    best_efficiency = 0
    
    for option in container_options:
        # Check if we have enough stock
        if option['available_quantity'] < option['containers_needed']:
            logger.info(f"Skipping {option['name']} - insufficient stock ({option['available_quantity']} < {option['containers_needed']})")
            continue
        
        # Calculate efficiency for this option
        total_container_capacity = option['capacity_in_yield_unit'] * option['containers_needed']
        efficiency = (total_yield / total_container_capacity) * 100 if total_container_capacity > 0 else 0
        
        # Apply efficiency tolerance - prefer containers within ±3% of 100% fill
        if efficiency >= (100 - EFFICIENCY_TOLERANCE * 100):  # 97% or better
            best_option = option
            best_efficiency = efficiency
            logger.info(f"Selected {option['name']} for optimal efficiency: {efficiency:.1f}%")
            break
        elif efficiency > best_efficiency:
            best_option = option
            best_efficiency = efficiency

    if not best_option:
        logger.warning(f"No containers have sufficient stock")
        return None

    # Create strategy with proper containment calculation
    total_capacity = best_option['capacity_in_yield_unit'] * best_option['containers_needed']
    containment_percentage = min(100.0, (total_yield / total_capacity) * 100) if total_capacity > 0 else 0

    # Issue partial fill warning if significantly under-filled
    warnings = []
    if containment_percentage < 50:
        warnings.append(f"Low fill efficiency: {containment_percentage:.1f}% - consider smaller containers")

    container_strategy = ContainerStrategy(
        selected_containers=[ContainerOption(
            container_id=best_option['id'],
            container_name=best_option['name'],
            capacity=best_option['capacity'],
            available_quantity=best_option['available_quantity'],
            containers_needed=best_option['containers_needed'],
            cost_each=0.0  # TODO: Add cost calculation
        )],
        total_capacity=total_capacity,
        containment_percentage=containment_percentage,
        fill_strategy=ContainerFillStrategy(
            selected_containers=[best_option],
            total_capacity=total_capacity,
            containment_percentage=containment_percentage,
            strategy_type="auto"
        ),
        warnings=warnings
    )

    logger.info(f"Created auto-fill strategy: {best_option['name']} x{best_option['containers_needed']} = {containment_percentage:.1f}% fill")
    return container_strategy


def get_container_plan_for_api(recipe_id: int, scale: float) -> Dict[str, Any]:
    """
    API endpoint for container planning - returns JSON-ready data with proper unit conversion.
    """
    try:
        from ...models import Recipe

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return {'success': False, 'error': 'Recipe not found'}

        org_id = current_user.organization_id if current_user.is_authenticated else None

        strategy, options = analyze_container_options(recipe, scale, None, org_id)

        if not strategy and not options:
            return {
                'success': False,
                'error': 'No suitable containers found for this recipe. Please check that containers are assigned to this recipe and have proper storage capacity.'
            }

        if strategy:
            # Format response with proper unit display for frontend
            container_selection = []
            for opt in strategy.selected_containers:
                # Find original option data for detailed capacity info
                original_option = next((o for o in options if o['id'] == opt.container_id), None)
                
                container_data = {
                    'id': opt.container_id,
                    'name': opt.container_name,
                    'capacity': opt.capacity,  # Original storage capacity
                    'unit': original_option.get('unit', 'ml') if original_option else 'ml',
                    'quantity': opt.containers_needed,
                    'stock_qty': opt.available_quantity,
                    'available_quantity': opt.available_quantity
                }
                
                # Add converted capacity info for proper display
                if original_option:
                    container_data.update({
                        'capacity_in_yield_unit': original_option.get('capacity_in_yield_unit'),
                        'yield_unit': original_option.get('yield_unit'),
                        'conversion_successful': original_option.get('conversion_successful', False),
                        'total_yield_needed': (recipe.predicted_yield or 0) * scale
                    })
                
                container_selection.append(container_data)

            return {
                'success': True,
                'container_selection': container_selection,
                'total_capacity': strategy.total_capacity,
                'containment_percentage': strategy.containment_percentage,
                'warnings': strategy.warnings
            }
        else:
            return {
                'success': False,
                'error': 'Insufficient container stock for required yield',
                'available_options': options,
                'required_yield': (recipe.predicted_yield or 0) * scale
            }

    except Exception as e:
        logger.error(f"Error in get_container_plan_for_api: {e}")
        return {'success': False, 'error': str(e)}
