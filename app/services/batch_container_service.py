
from typing import Dict, List, Tuple
from app.models import Batch, BatchContainer
from app.extensions import db

class BatchContainerService:
    
    @staticmethod
    def get_container_summary(batch_id: int) -> Dict:
        """Get comprehensive container summary for a batch"""
        containers = BatchContainer.query.filter_by(batch_id=batch_id).all()
        
        total_capacity = 0
        valid_containers = []
        broken_containers = []
        
        for container in containers:
            if container.is_valid_for_product:
                valid_containers.append(container)
                total_capacity += container.total_capacity
            else:
                broken_containers.append(container)
        
        return {
            'valid_containers': valid_containers,
            'broken_containers': broken_containers,
            'total_capacity': total_capacity,
            'container_count': len(valid_containers),
            'broken_count': len(broken_containers)
        }
    
    @staticmethod
    def validate_yield_vs_capacity(batch_id: int, actual_yield: float) -> Dict:
        """Validate if yield matches container capacity and provide guidance"""
        summary = BatchContainerService.get_container_summary(batch_id)
        total_capacity = summary['total_capacity']
        
        validation = {
            'is_valid': True,
            'warnings': [],
            'overflow_amount': 0,
            'underfill_amount': 0
        }
        
        if actual_yield > total_capacity:
            overflow = actual_yield - total_capacity
            validation['warnings'].append(
                f"You have {overflow:.2f} units more product than your containers can hold. "
                f"This will be stored as bulk."
            )
            validation['overflow_amount'] = overflow
            
        elif actual_yield < total_capacity * 0.8:  # Less than 80% fill
            underfill = total_capacity - actual_yield
            validation['warnings'].append(
                f"Your containers will have {underfill:.2f} units of unused space. "
                f"Consider using smaller containers or expect underfilled products."
            )
            validation['underfill_amount'] = underfill
        
        if summary['broken_count'] > 0:
            validation['warnings'].append(
                f"{summary['broken_count']} container(s) were broken and excluded from final product count."
            )
        
        return validation
    
    @staticmethod
    def generate_product_records(batch_id: int, product_id: int, variant_id: int, actual_yield: float) -> List[Dict]:
        """Generate product records based on valid containers and yield"""
        summary = BatchContainerService.get_container_summary(batch_id)
        validation = BatchContainerService.validate_yield_vs_capacity(batch_id, actual_yield)
        
        product_records = []
        
        # Create records for each valid container
        for container in summary['valid_containers']:
            for _ in range(int(container.quantity_used)):
                product_records.append({
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'container_name': container.container_name,
                    'container_size': container.container_size,
                    'fill_amount': min(container.container_size, actual_yield / summary['container_count']),
                    'batch_id': batch_id
                })
        
        # Handle overflow as bulk
        if validation['overflow_amount'] > 0:
            product_records.append({
                'product_id': product_id,
                'variant_id': variant_id,
                'container_name': 'Bulk',
                'container_size': validation['overflow_amount'],
                'fill_amount': validation['overflow_amount'],
                'batch_id': batch_id,
                'is_bulk': True
            })
        
        return product_records
