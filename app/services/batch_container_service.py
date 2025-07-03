from typing import Dict, List
from app.models import BatchContainer, ExtraBatchContainer
from app.extensions import db

class BatchContainerService:

    @staticmethod
    def calculate_container_capacity(batch_id: int) -> float:
        """Calculate total container capacity for a batch"""
        regular_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch_id).all()

        total_capacity = 0
        
        # Process regular containers
        for container in regular_containers:
            total_capacity += (container.container.storage_amount or 0) * container.quantity_used

        # Process extra containers
        for extra_container in extra_containers:
            total_capacity += (extra_container.container.storage_amount or 0) * extra_container.quantity_used

        return total_capacity