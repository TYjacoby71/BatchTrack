
"""
Container Management for Production Planning

Single purpose: Find suitable containers, convert capacities, and provide greedy fill strategy.
"""

import logging
import math
from typing import List, Optional, Dict, Any, Tuple
from flask_login import current_user
from ...models import Recipe, InventoryItem

logger = logging.getLogger(__name__)


def analyze_container_options(
    recipe: Recipe, 
    scale: float, 
    preferred_container_id: Optional[int] = None, 
    organization_id: Optional[int] = None,
    api_format: bool = True
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Single entry point for container analysis.
    
    Returns:
        - Container strategy (greedy fill selection) 
        - All available container options
    """
    try:
        org_id = organization_id or (current_user.organization_id if current_user.is_authenticated else None)
        if not org_id:
            raise ValueError("Organization ID required")

        # Get recipe requirements
        total_yield = (recipe.predicted_yield or 0) * scale
        yield_unit = recipe.predicted_yield_unit or 'ml'
        
        if total_yield <= 0:
            raise ValueError(f"Recipe '{recipe.name}' has no predicted yield configured")

        # Load and filter containers
        container_options = _load_suitable_containers(recipe, org_id, total_yield, yield_unit)
        
        if not container_options:
            raise ValueError("No suitable containers found for this recipe")

        # Create greedy fill strategy
        strategy = _create_greedy_strategy(container_options, total_yield, yield_unit)
        
        return strategy, container_options

    except Exception as e:
        logger.error(f"Container analysis failed for recipe {recipe.id}: {e}")
        if api_format:
            return None, []
        raise


def _load_suitable_containers(recipe: Recipe, org_id: int, total_yield: float, yield_unit: str) -> List[Dict[str, Any]]:
    """Load containers allowed for this recipe and convert capacities"""
    
    # Get recipe's allowed containers - Recipe model uses 'allowed_containers' field
    allowed_container_ids = getattr(recipe, 'allowed_containers', [])
    
    # Debug logging to understand what's available
    logger.info(f"Recipe {recipe.id} container debug:")
    logger.info(f"  - allowed_containers: {allowed_container_ids}")
    logger.info(f"  - Recipe has allowed_containers field: {hasattr(recipe, 'allowed_containers')}")
    
    if not allowed_container_ids:
        raise ValueError(f"Recipe '{recipe.name}' has no containers configured")

    # Load containers from database in one query (avoid N+1)
    containers = InventoryItem.query.filter(
        InventoryItem.id.in_(allowed_container_ids),
        InventoryItem.organization_id == org_id,
        InventoryItem.quantity > 0
    ).all()

    container_options = []
    
    for container in containers:
        # Get container capacity
        storage_capacity = getattr(container, 'storage_amount', None)
        storage_unit = getattr(container, 'storage_unit', None)

        if not storage_capacity or not storage_unit:
            logger.warning(f"Container {container.name} missing capacity data")
            continue

        # Convert capacity to recipe yield units
        converted_capacity = _convert_capacity(storage_capacity, storage_unit, yield_unit)
        if converted_capacity <= 0:
            logger.warning(f"Container {container.name} capacity conversion failed")
            continue

        container_options.append({
            'container_id': container.id,
            'container_name': container.name,
            'capacity': converted_capacity,  # Always in recipe yield units
            'original_capacity': storage_capacity,
            'original_unit': storage_unit,
            'available_quantity': int(container.quantity or 0),
            'containers_needed': 0,  # Will be set by strategy
            'cost_each': 0.0
        })

    # Sort by capacity (largest first for greedy algorithm)
    container_options.sort(key=lambda x: x['capacity'], reverse=True)
    
    return container_options


def _convert_capacity(capacity: float, from_unit: str, to_unit: str) -> float:
    """Convert container capacity to recipe yield units"""
    if from_unit == to_unit:
        return capacity

    try:
        from ...services.unit_conversion import ConversionEngine
        result = ConversionEngine.convert_units(capacity, from_unit, to_unit)
        return result['converted_value'] if isinstance(result, dict) else float(result)
    except Exception as e:
        logger.warning(f"Cannot convert {capacity} {from_unit} to {to_unit}: {e}")
        return 0.0


def _create_greedy_strategy(container_options: List[Dict[str, Any]], total_yield: float, yield_unit: str) -> Dict[str, Any]:
    """Create greedy fill strategy - largest containers first"""
    
    selected_containers = []
    remaining_yield = total_yield

    for container in container_options:
        if remaining_yield <= 0:
            break

        # Calculate how many of this container we need
        containers_needed = min(
            container['available_quantity'],
            math.ceil(remaining_yield / container['capacity'])
        )

        if containers_needed > 0:
            # Update the container option with selection
            container['containers_needed'] = containers_needed
            selected_containers.append(container.copy())
            remaining_yield -= containers_needed * container['capacity']

    # Calculate totals
    total_capacity = sum(c['capacity'] * c['containers_needed'] for c in selected_containers)
    containment_percentage = min(100.0, (total_yield / total_capacity * 100) if total_capacity > 0 else 0)

    # Create warnings
    warnings = []
    if containment_percentage < 80:
        warnings.append(f"Low fill efficiency: {containment_percentage:.1f}%. Consider different container sizes.")
    
    if remaining_yield > 0:
        warnings.append(f"Insufficient capacity: {remaining_yield:.1f} {yield_unit} remaining")

    return {
        'success': True,
        'container_selection': selected_containers,
        'total_capacity': total_capacity,
        'containment_percentage': containment_percentage,
        'warnings': warnings,
        'strategy_type': 'greedy_fill'
    }
