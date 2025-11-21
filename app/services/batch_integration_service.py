
from typing import Optional, Dict, Any, List
from ..services.inventory_adjustment import process_inventory_adjustment
from ..models import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, InventoryItem, db
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

class BatchIntegrationService:
    """Simplified service for batch operations that integrates with inventory system"""

    @staticmethod
    def consume_ingredients(batch: Batch, ingredient_consumption: Dict[str, float]) -> bool:
        """Consume ingredients for batch production using inventory adjustment"""
        try:
            for item_id, quantity in ingredient_consumption.items():
                result = process_inventory_adjustment(
                    inventory_item_id=item_id,
                    quantity_delta=-quantity,  # Negative for consumption
                    adjustment_type='batch_consumption',
                    reason=f'Consumed for batch {batch.batch_number}',
                    user_id=batch.created_by,
                    organization_id=batch.organization_id,
                    batch_id=batch.id
                )

                if not result['success']:
                    logger.error(f"Failed to consume ingredient {item_id} for batch {batch.id}: {result.get('error')}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error consuming ingredients for batch {batch.id}: {str(e)}")
            return False

    @staticmethod
    def finish_batch(batch: Batch, output_sku_id: str, output_quantity: float) -> bool:
        """Finish batch and credit output using inventory adjustment"""
        try:
            result = process_inventory_adjustment(
                inventory_item_id=output_sku_id,
                quantity_delta=output_quantity,  # Positive for production
                adjustment_type='batch_finish',
                reason=f'Finished batch {batch.batch_number}',
                user_id=batch.created_by,
                organization_id=batch.organization_id,
                batch_id=batch.id
            )

            if not result['success']:
                logger.error(f"Failed to credit output for finished batch {batch.id}: {result.get('error')}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error finishing batch {batch.id}: {str(e)}")
            return False

    def get_batch_containers_summary(self, batch_id: int) -> Dict[str, Any]:
        """Get container summary for a batch"""
        try:
            batch = Batch.scoped().filter_by(id=batch_id).first()
            if not batch:
                return {'success': False, 'error': 'Batch not found'}

            # Get regular containers
            containers = BatchContainer.query.filter_by(
                batch_id=batch_id,
                organization_id=current_user.organization_id
            ).all()

            # Get extra containers
            extra_containers = ExtraBatchContainer.query.filter_by(
                batch_id=batch_id,
                organization_id=current_user.organization_id
            ).all()

            container_data = []
            total_capacity = 0

            # Process regular containers
            for container in containers:
                capacity = (container.inventory_item.capacity or 0) * container.quantity_used
                container_info = {
                    'id': container.id,
                    'name': container.inventory_item.container_display_name if container.inventory_item else 'Unknown',
                    'quantity': container.quantity_used,
                    'capacity': capacity,
                    'type': 'regular'
                }
                container_data.append(container_info)
                total_capacity += capacity

            # Process extra containers
            for extra_container in extra_containers:
                capacity = (extra_container.inventory_item.capacity or 0) * extra_container.quantity_used
                container_info = {
                    'id': extra_container.id,
                    'name': extra_container.inventory_item.container_display_name if extra_container.inventory_item else 'Unknown',
                    'quantity': extra_container.quantity_used,
                    'reason': extra_container.reason,
                    'capacity': capacity,
                    'type': 'extra'
                }
                container_data.append(container_info)
                total_capacity += capacity

            summary = {
                'total_containers': len(container_data),
                'total_capacity': total_capacity,
                'capacity_unit': batch.projected_yield_unit or 'fl oz'
            }

            return {
                'success': True,
                'data': {
                    'containers': container_data,
                    'summary': summary
                }
            }

        except Exception as e:
            logger.error(f"Error getting batch containers: {e}")
            return {'success': False, 'error': str(e)}

    def remove_container_from_batch(self, batch_id: int, container_id: int) -> Dict[str, Any]:
        """Remove a container from batch and restore inventory"""
        try:
            # Find container record (regular or extra)
            container = BatchContainer.query.filter_by(
                id=container_id,
                batch_id=batch_id,
                organization_id=current_user.organization_id
            ).first()

            if not container:
                container = ExtraBatchContainer.query.filter_by(
                    id=container_id,
                    batch_id=batch_id,
                    organization_id=current_user.organization_id
                ).first()

            if not container:
                return {'success': False, 'error': 'Container not found'}

            # Restore inventory using inventory adjustment
            result = process_inventory_adjustment(
                inventory_item_id=container.container_id,
                quantity_delta=container.quantity_used,  # Positive to restore
                adjustment_type='batch_correction',
                reason=f"Restored container from batch {batch_id}",
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                batch_id=batch_id
            )

            if not result['success']:
                return {'success': False, 'error': f"Failed to restore inventory: {result.get('error')}"}

            db.session.delete(container)
            db.session.commit()

            return {'success': True, 'message': 'Container removed successfully'}

        except Exception as e:
            logger.error(f"Error removing container: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def adjust_batch_container(self, batch_id: int, container_id: int,
                              adjustment_type: str, adjustment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust container quantity or type using inventory adjustment"""
        try:
            # Find container record
            container_record = BatchContainer.query.filter_by(
                id=container_id,
                batch_id=batch_id,
                organization_id=current_user.organization_id
            ).first()

            if not container_record:
                container_record = ExtraBatchContainer.query.filter_by(
                    id=container_id,
                    batch_id=batch_id,
                    organization_id=current_user.organization_id
                ).first()

            if not container_record:
                return {'success': False, 'error': 'Container not found'}

            # All adjustments go through inventory adjustment system
            if adjustment_type == 'quantity':
                return self._adjust_quantity_via_inventory(container_record, batch_id, adjustment_data)
            elif adjustment_type == 'replace':
                return self._replace_via_inventory(container_record, batch_id, adjustment_data)
            else:
                return {'success': False, 'error': 'Invalid adjustment type'}

        except Exception as e:
            logger.error(f"Error adjusting container: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def _adjust_quantity_via_inventory(self, container_record, batch_id, data):
        """Adjust container quantity using inventory adjustment"""
        new_total = data.get('new_total_quantity', 0)
        current_qty = container_record.quantity_used
        quantity_difference = new_total - current_qty

        if quantity_difference != 0:
            result = process_inventory_adjustment(
                inventory_item_id=container_record.container_id,
                quantity_delta=quantity_difference,  # Positive = return, Negative = use more
                adjustment_type='batch_adjustment',
                reason=f"Container quantity adjustment for batch {batch_id}: {data.get('notes', '')}",
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                batch_id=batch_id
            )

            if not result['success']:
                return {'success': False, 'error': f"Inventory adjustment failed: {result.get('error')}"}

        container_record.quantity_used = new_total
        db.session.commit()
        return {'success': True, 'message': 'Container quantity adjusted'}

    def _replace_via_inventory(self, container_record, batch_id, data):
        """Replace container type using inventory adjustment"""
        new_container_id = data.get('new_container_id')
        new_quantity = data.get('new_quantity', 1)

        if not new_container_id:
            return {'success': False, 'error': 'New container must be selected'}

        # Return old containers
        result1 = process_inventory_adjustment(
            inventory_item_id=container_record.container_id,
            quantity_delta=container_record.quantity_used,
            adjustment_type='batch_correction',
            reason=f"Container replacement return for batch {batch_id}: {data.get('notes', '')}",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            batch_id=batch_id
        )

        if not result1['success']:
            return {'success': False, 'error': f"Failed to return old containers: {result1.get('error')}"}

        # Deduct new containers
        result2 = process_inventory_adjustment(
            inventory_item_id=new_container_id,
            quantity_delta=-new_quantity,
            adjustment_type='batch_consumption',
            reason=f"Container replacement for batch {batch_id}: {data.get('notes', '')}",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            batch_id=batch_id
        )

        if not result2['success']:
            # Rollback by returning the old containers
            process_inventory_adjustment(
                inventory_item_id=container_record.container_id,
                quantity_delta=-container_record.quantity_used,
                adjustment_type='batch_consumption',
                reason=f"Rollback for failed replacement in batch {batch_id}",
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                batch_id=batch_id
            )
            return {'success': False, 'error': f"Failed to deduct new containers: {result2.get('error')}"}

        # Update container record
        new_container = db.session.get(InventoryItem, new_container_id)
        container_record.container_id = new_container_id
        container_record.quantity_used = new_quantity
        container_record.cost_each = new_container.cost_per_unit or 0.0

        db.session.commit()
        return {'success': True, 'message': 'Container replaced successfully'}
