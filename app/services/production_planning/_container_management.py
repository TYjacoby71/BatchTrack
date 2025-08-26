
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
    Create intelligent multi-container auto-fill strategy using bin packing optimization.
    
    Strategy:
    1. Find optimal combination of containers that minimizes waste
    2. Use bin packing algorithm to try different combinations
    3. Prefer combinations that get closest to 100% efficiency
    4. Fall back to single container if multi-container doesn't improve efficiency
    """
    
    if not container_options:
        return None

    # Filter containers with sufficient stock
    available_containers = []
    for option in container_options:
        if option['available_quantity'] > 0 and option['capacity_in_yield_unit'] > 0:
            available_containers.append(option)
    
    if not available_containers:
        logger.warning("No containers have sufficient stock")
        return None

    # Try multi-container optimization first
    best_combination = _find_optimal_container_combination(available_containers, total_yield)
    
    if best_combination:
        logger.info(f"Multi-container optimization found: {len(best_combination['containers'])} container types")
        return _create_strategy_from_combination(best_combination, total_yield, yield_unit)
    
    # Fall back to single container approach
    logger.info("Falling back to single container selection")
    return _create_single_container_strategy(available_containers, total_yield, yield_unit)


def _find_optimal_container_combination(
    containers: List[Dict[str, Any]], 
    target_yield: float
) -> Optional[Dict[str, Any]]:
    """
    Find optimal combination of containers using bin packing algorithm.
    
    Returns best combination that minimizes waste while staying within stock limits.
    """
    
    # Sort containers by capacity (largest first for efficiency)
    sorted_containers = sorted(containers, key=lambda x: x['capacity_in_yield_unit'], reverse=True)
    
    best_combination = None
    best_efficiency = 0
    best_waste = float('inf')
    
    # Try different combinations using recursive bin packing
    for max_types in range(1, min(4, len(sorted_containers) + 1)):  # Limit to 3 container types max
        combination = _bin_pack_containers(sorted_containers, target_yield, max_types)
        
        if combination:
            total_capacity = sum(c['capacity_in_yield_unit'] * c['quantity_used'] for c in combination)
            efficiency = (target_yield / total_capacity) * 100 if total_capacity > 0 else 0
            waste = total_capacity - target_yield
            
            # Prefer combinations with efficiency >= 97% or minimal waste
            if (efficiency >= 97.0 or 
                (efficiency > best_efficiency and waste < best_waste) or
                (abs(efficiency - 100) < abs(best_efficiency - 100))):
                
                best_combination = {
                    'containers': combination,
                    'total_capacity': total_capacity,
                    'efficiency': efficiency,
                    'waste': waste
                }
                best_efficiency = efficiency
                best_waste = waste
                
                # If we found near-perfect efficiency, use it
                if efficiency >= 99.0:
                    break
    
    return best_combination


def _bin_pack_containers(
    containers: List[Dict[str, Any]], 
    remaining_yield: float, 
    max_types: int,
    current_combination: Optional[List[Dict[str, Any]]] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Recursive bin packing to find optimal container combination.
    """
    
    if current_combination is None:
        current_combination = []
    
    if remaining_yield <= 0:
        return current_combination
    
    if len(current_combination) >= max_types:
        return None
    
    best_solution = None
    best_waste = float('inf')
    
    for i, container in enumerate(containers):
        # Skip if already used this container type
        if any(c['id'] == container['id'] for c in current_combination):
            continue
            
        capacity = container['capacity_in_yield_unit']
        stock_limit = container['available_quantity']
        
        # Try different quantities of this container
        for qty in range(1, min(stock_limit + 1, int(remaining_yield / capacity) + 2)):
            container_contribution = capacity * qty
            
            # Add this container to combination
            new_combination = current_combination + [{
                'id': container['id'],
                'name': container['name'],
                'capacity': container['capacity'],
                'unit': container['unit'],
                'capacity_in_yield_unit': capacity,
                'yield_unit': container.get('yield_unit', 'ml'),
                'available_quantity': container['available_quantity'],
                'quantity_used': qty,
                'conversion_successful': container.get('conversion_successful', True)
            }]
            
            new_remaining = remaining_yield - container_contribution
            
            if new_remaining <= 0:
                # This combination covers the yield
                waste = abs(new_remaining)
                if waste < best_waste:
                    best_solution = new_combination
                    best_waste = waste
            else:
                # Try to fill remaining with other containers
                remaining_containers = containers[i+1:]
                if remaining_containers:
                    recursive_solution = _bin_pack_containers(
                        remaining_containers, new_remaining, max_types, new_combination
                    )
                    if recursive_solution:
                        total_capacity = sum(c['capacity_in_yield_unit'] * c['quantity_used'] for c in recursive_solution)
                        waste = total_capacity - remaining_yield
                        if waste >= 0 and waste < best_waste:
                            best_solution = recursive_solution
                            best_waste = waste
    
    return best_solution


def _create_strategy_from_combination(
    combination: Dict[str, Any], 
    total_yield: float, 
    yield_unit: str
) -> ContainerStrategy:
    """Create strategy from optimal container combination."""
    
    selected_containers = []
    total_capacity = combination['total_capacity']
    efficiency = combination['efficiency']
    
    for container_data in combination['containers']:
        selected_containers.append(ContainerOption(
            container_id=container_data['id'],
            container_name=container_data['name'],
            capacity=container_data['capacity'],
            available_quantity=container_data['available_quantity'],
            containers_needed=container_data['quantity_used'],
            cost_each=0.0  # TODO: Add cost calculation
        ))
    
    containment_percentage = min(100.0, efficiency)
    
    # Generate optimization messages
    warnings = []
    if len(combination['containers']) > 1:
        container_summary = ", ".join([
            f"{c['name']} x{c['quantity_used']}" for c in combination['containers']
        ])
        warnings.append(f"Multi-container optimization: {container_summary}")
    
    if efficiency < 90:
        warnings.append(f"Fill efficiency: {efficiency:.1f}% - consider smaller containers if available")
    
    # Format selected containers for API response
    formatted_containers = []
    for container_data in combination['containers']:
        formatted_containers.append({
            'id': container_data['id'],
            'name': container_data['name'],
            'capacity': container_data['capacity'],
            'unit': container_data['unit'],
            'capacity_in_yield_unit': container_data['capacity_in_yield_unit'],
            'yield_unit': container_data['yield_unit'],
            'quantity': container_data['quantity_used'],
            'available_quantity': container_data['available_quantity'],
            'conversion_successful': container_data['conversion_successful'],
            'containers_needed': container_data['quantity_used'],
            'total_yield_needed': total_yield
        })
    
    container_strategy = ContainerStrategy(
        selected_containers=selected_containers,
        total_capacity=total_capacity,
        containment_percentage=containment_percentage,
        fill_strategy=ContainerFillStrategy(
            selected_containers=formatted_containers,
            total_capacity=total_capacity,
            containment_percentage=containment_percentage,
            strategy_type="auto_optimized"
        ),
        warnings=warnings
    )

    logger.info(f"Created optimized strategy: {efficiency:.1f}% efficiency with {len(combination['containers'])} container types")
    return container_strategy


def _create_single_container_strategy(
    containers: List[Dict[str, Any]], 
    total_yield: float, 
    yield_unit: str
) -> Optional[ContainerStrategy]:
    """Fallback to single container selection."""
    
    best_option = None
    best_efficiency = 0
    
    for option in containers:
        containers_needed = max(1, int(math.ceil(total_yield / option['capacity_in_yield_unit'])))
        
        if option['available_quantity'] < containers_needed:
            continue
        
        total_container_capacity = option['capacity_in_yield_unit'] * containers_needed
        efficiency = (total_yield / total_container_capacity) * 100 if total_container_capacity > 0 else 0
        
        if efficiency >= (100 - EFFICIENCY_TOLERANCE * 100):  # 97% or better
            best_option = option
            best_option['containers_needed'] = containers_needed
            best_efficiency = efficiency
            break
        elif efficiency > best_efficiency:
            best_option = option
            best_option['containers_needed'] = containers_needed
            best_efficiency = efficiency

    if not best_option:
        return None

    total_capacity = best_option['capacity_in_yield_unit'] * best_option['containers_needed']
    containment_percentage = min(100.0, (total_yield / total_capacity) * 100) if total_capacity > 0 else 0

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
            cost_each=0.0
        )],
        total_capacity=total_capacity,
        containment_percentage=containment_percentage,
        fill_strategy=ContainerFillStrategy(
            selected_containers=[{
                'id': best_option['id'],
                'name': best_option['name'],
                'capacity': best_option['capacity'],
                'unit': best_option['unit'],
                'capacity_in_yield_unit': best_option['capacity_in_yield_unit'],
                'yield_unit': best_option.get('yield_unit', yield_unit),
                'quantity': best_option['containers_needed'],
                'available_quantity': best_option['available_quantity'],
                'conversion_successful': best_option.get('conversion_successful', True),
                'containers_needed': best_option['containers_needed'],
                'total_yield_needed': total_yield
            }],
            total_capacity=total_capacity,
            containment_percentage=containment_percentage,
            strategy_type="auto_single"
        ),
        warnings=warnings
    )

    logger.info(f"Single container strategy: {best_option['name']} x{best_option['containers_needed']} = {containment_percentage:.1f}% fill")
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
