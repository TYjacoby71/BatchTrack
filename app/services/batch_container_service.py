from typing import Dict, List
from app.models import BatchContainer
from app.extensions import db

class BatchContainerService:

    @staticmethod
    def validate_yield_vs_capacity(batch_id: int, estimated_yield: float) -> Dict:
        """Validate if yield matches container capacity and provide guidance"""
        # Get containers actually used in this batch
        containers = BatchContainer.query.filter_by(batch_id=batch_id).all()

        total_capacity = 0
        container_breakdown = []

        for container in containers:
            container_capacity = (container.container.storage_amount or 0) * container.quantity_used
            total_capacity += container_capacity

            container_breakdown.append({
                'container_name': container.container.name,
                'container_size': container.container.storage_amount or 0,
                'quantity_used': container.quantity_used,
                'total_capacity': container_capacity
            })

        validation = {
            'is_valid': True,
            'warnings': [],
            'overflow_amount': 0,
            'underfill_amount': 0,
            'total_capacity': total_capacity,
            'container_breakdown': container_breakdown
        }

        if estimated_yield > total_capacity:
            overflow = estimated_yield - total_capacity
            validation['warnings'].append(
                f"You have {overflow:.2f} units more product than your containers can hold. "
                f"Excess will be stored as bulk product."
            )
            validation['overflow_amount'] = overflow

        elif estimated_yield < total_capacity * 0.8:  # Less than 80% fill
            underfill = total_capacity - estimated_yield
            validation['warnings'].append(
                f"Your containers will have {underfill:.2f} units of unused space. "
                f"Consider if some containers were broken or if yield was lower than expected."
            )
            validation['underfill_amount'] = underfill

        return validation