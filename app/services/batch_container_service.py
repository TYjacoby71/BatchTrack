from typing import Dict, List
from app.models import BatchContainer, ExtraBatchContainer
from app.extensions import db

class BatchContainerService:

    @staticmethod
    def validate_yield_vs_capacity(batch_id: int, estimated_yield: float) -> Dict:
        """Validate if yield matches container capacity and provide guidance"""
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