
"""
Container Management Service for Production Planning

This service handles container selection and optimization for batch production.
All business logic for container calculations resides here.
"""

from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal, ROUND_UP
import logging

from app.models import Container, Recipe
from app.utils.unit_utils import convert_units
from .types import ContainerOption, ContainerStrategy

logger = logging.getLogger(__name__)


class ContainerManagementService:
    """Service for managing container selection and optimization"""
    
    @staticmethod
    def analyze_container_options(recipe: Recipe, scale_factor: float = 1.0) -> Dict[str, Any]:
        """
        Analyze container options for a recipe at given scale.
        
        Returns structured data with all valid containers and auto-fill recommendation.
        """
        try:
            # Calculate total yield needed
            base_yield = float(recipe.predicted_yield or 0)
            total_yield = base_yield * scale_factor
            yield_unit = recipe.predicted_yield_unit or 'units'
            
            if total_yield <= 0:
                return {
                    "success": False,
                    "error": "Invalid recipe yield or scale factor",
                    "all_container_options": [],
                    "auto_fill_strategy": None
                }
            
            logger.info(f"Analyzing containers for {total_yield} {yield_unit}")
            
            # Get all valid containers
            all_container_options = ContainerManagementService._get_all_valid_containers(
                total_yield, yield_unit
            )
            
            if not all_container_options:
                return {
                    "success": False,
                    "error": "No suitable containers found",
                    "all_container_options": [],
                    "auto_fill_strategy": None
                }
            
            # Create auto-fill strategy using greedy algorithm
            auto_fill_strategy = ContainerManagementService._create_auto_fill_strategy(
                all_container_options, total_yield
            )
            
            return {
                "success": True,
                "all_container_options": [opt.to_dict() for opt in all_container_options],
                "auto_fill_strategy": auto_fill_strategy
            }
            
        except Exception as e:
            logger.error(f"Error analyzing container options: {e}")
            return {
                "success": False,
                "error": str(e),
                "all_container_options": [],
                "auto_fill_strategy": None
            }
    
    @staticmethod
    def _get_all_valid_containers(total_yield: float, yield_unit: str) -> List[ContainerOption]:
        """Get all containers that could potentially be used for this yield"""
        containers = Container.query.filter_by(is_active=True).all()
        valid_options = []
        
        for container in containers:
            try:
                # Convert container capacity to yield units
                capacity_in_yield_units = convert_units(
                    container.capacity,
                    container.capacity_unit,
                    yield_unit
                )
                
                if capacity_in_yield_units and capacity_in_yield_units > 0:
                    # Calculate how many containers would be needed
                    containers_needed = int((total_yield / capacity_in_yield_units) + 0.999)  # Ceiling
                    
                    # Calculate total capacity if using this container type
                    total_capacity = capacity_in_yield_units * containers_needed
                    containment_percentage = (total_capacity / total_yield) * 100
                    
                    # Calculate fill efficiency of last container
                    if containers_needed == 1:
                        last_container_fill = (total_yield / capacity_in_yield_units) * 100
                    else:
                        remaining_after_full_containers = total_yield - (capacity_in_yield_units * (containers_needed - 1))
                        last_container_fill = (remaining_after_full_containers / capacity_in_yield_units) * 100
                    
                    valid_options.append(ContainerOption(
                        container_id=container.id,
                        container_name=container.name,
                        capacity=capacity_in_yield_units,
                        capacity_unit=yield_unit,
                        containers_needed=containers_needed,
                        total_capacity=total_capacity,
                        containment_percentage=containment_percentage,
                        last_container_fill_percentage=last_container_fill
                    ))
                    
            except Exception as e:
                logger.warning(f"Error processing container {container.name}: {e}")
                continue
        
        # Sort by efficiency (prefer higher fill percentages and fewer containers)
        valid_options.sort(key=lambda x: (-x.last_container_fill_percentage, x.containers_needed))
        
        return valid_options
    
    @staticmethod
    def _create_auto_fill_strategy(container_options: List[ContainerOption], total_yield: float) -> Optional[Dict[str, Any]]:
        """
        Create auto-fill strategy using greedy algorithm to find most efficient combination
        """
        if not container_options:
            return None
        
        # For now, use the most efficient single container type
        # TODO: Implement true greedy algorithm for mixed container types
        best_option = container_options[0]  # Already sorted by efficiency
        
        containers_to_use = []
        for i in range(best_option.containers_needed):
            containers_to_use.append({
                "container_id": best_option.container_id,
                "container_name": best_option.container_name,
                "capacity": best_option.capacity,
                "capacity_unit": best_option.capacity_unit,
                "fill_percentage": 100.0 if i < best_option.containers_needed - 1 else best_option.last_container_fill_percentage
            })
        
        return {
            "containers_to_use": containers_to_use,
            "metrics": {
                "containment_percentage": best_option.containment_percentage,
                "last_container_fill_percentage": best_option.last_container_fill_percentage,
                "total_containers": best_option.containers_needed,
                "total_capacity": best_option.total_capacity
            }
        }
    
    @staticmethod
    def calculate_container_metrics(selected_containers: List[Dict], total_yield: float) -> Dict[str, Any]:
        """
        Calculate metrics for manually selected containers
        """
        if not selected_containers:
            return {
                "containment_percentage": 0,
                "last_container_fill_percentage": 0,
                "total_containers": 0,
                "total_capacity": 0
            }
        
        total_capacity = sum(float(c.get('capacity', 0)) for c in selected_containers)
        containment_percentage = (total_capacity / total_yield) * 100 if total_yield > 0 else 0
        
        # Calculate last container fill
        if len(selected_containers) == 1:
            last_container_fill = (total_yield / total_capacity) * 100 if total_capacity > 0 else 0
        else:
            # Assume containers are filled in order
            last_container = selected_containers[-1]
            last_capacity = float(last_container.get('capacity', 0))
            previous_capacity = sum(float(c.get('capacity', 0)) for c in selected_containers[:-1])
            remaining_yield = max(0, total_yield - previous_capacity)
            last_container_fill = (remaining_yield / last_capacity) * 100 if last_capacity > 0 else 0
        
        return {
            "containment_percentage": containment_percentage,
            "last_container_fill_percentage": min(100, last_container_fill),
            "total_containers": len(selected_containers),
            "total_capacity": total_capacity
        }
