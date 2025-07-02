from typing import Dict, List
from app.models import BatchContainer, ExtraBatchContainer
from app.extensions import db

class BatchContainerService:

    @staticmethod
    def validate_yield_vs_capacity(batch_id: int, estimated_yield: float) -> Dict:
        """Validate if yield matches container capacity and provide guidance"""
        try:
            # Get both regular and extra containers used in this batch
            regular_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()
            extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch_id).all()

            total_capacity = 0
            container_breakdown = []

            # Process regular containers
            for container in regular_containers:
                container_capacity = (container.container.storage_amount or 0) * container.quantity_used
                total_capacity += container_capacity

                container_breakdown.append({
                    'container_name': container.container.name,
                    'container_size': container.container.storage_amount or 0,
                    'quantity_used': container.quantity_used,
                    'total_capacity': container_capacity,
                    'container_type': 'regular'
                })

            # Process extra containers
            for extra_container in extra_containers:
                container_capacity = (extra_container.container.storage_amount or 0) * extra_container.quantity_used
                total_capacity += container_capacity

                container_breakdown.append({
                    'container_name': extra_container.container.name,
                    'container_size': extra_container.container.storage_amount or 0,
                    'quantity_used': extra_container.quantity_used,
                    'total_capacity': container_capacity,
                    'container_type': 'extra',
                    'reason': getattr(extra_container, 'reason', 'extra_yield')
                })

            validation = {
                'total_capacity': total_capacity,
                'estimated_yield': estimated_yield,
                'container_breakdown': container_breakdown,
                'warnings': [],
                'overflow_amount': max(0, estimated_yield - total_capacity),
                'underfill_amount': max(0, total_capacity - estimated_yield)
            }

            # Add warnings based on capacity vs yield
            if estimated_yield > total_capacity:
                validation['warnings'].append(
                    f"Yield ({estimated_yield}) exceeds container capacity ({total_capacity}). "
                    f"Consider adding more containers or reducing yield."
                )
            elif estimated_yield < total_capacity * 0.8:  # Less than 80% capacity
                validation['warnings'].append(
                    f"Yield ({estimated_yield}) is significantly less than container capacity ({total_capacity}). "
                    f"Consider using smaller containers for better efficiency."
                )

            return validation

        except Exception as e:
            # Return a safe fallback response on any error
            return {
                'total_capacity': 0,
                'estimated_yield': estimated_yield,
                'container_breakdown': [],
                'warnings': [f"Error validating containers: {str(e)}"],
                'overflow_amount': 0,
                'underfill_amount': 0
            }