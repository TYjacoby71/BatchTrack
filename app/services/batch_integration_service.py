from typing import Optional, Dict, Any
from ..services.inventory_adjustment import process_inventory_adjustment
from ..models import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, InventoryItem, db
import logging

logger = logging.getLogger(__name__)

class BatchIntegrationService:
    """Service for batch operations that affect inventory"""

    @staticmethod
    def consume_ingredients(batch: Batch, ingredient_consumption: Dict[str, float]) -> bool:
        """
        Consume ingredients for batch production

        Args:
            batch: The batch being processed
            ingredient_consumption: Dict of {inventory_item_id: quantity_to_consume}

        Returns:
            bool: Success status
        """
        try:
            for item_id, quantity in ingredient_consumption.items():
                inventory_item = InventoryItem.query.get(item_id)
                if not inventory_item:
                    logger.error(f"Inventory item {item_id} not found for batch {batch.id}")
                    continue

                # Use canonical inventory adjustment service
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
        """
        Finish batch and credit output to inventory

        Args:
            batch: The batch being finished
            output_sku_id: SKU to credit with finished product
            output_quantity: Quantity of finished product

        Returns:
            bool: Success status
        """
        try:
            # Use canonical inventory adjustment service
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

    @staticmethod
    def dispose_batch(batch: Batch, reason: str) -> bool:
        """
        Dispose of batch without crediting inventory

        Args:
            batch: The batch being disposed
            reason: Reason for disposal

        Returns:
            bool: Success status
        """
        try:
            # Log disposal but no inventory adjustment needed
            logger.info(f"Batch {batch.batch_number} disposed: {reason}")
            return True

        except Exception as e:
            logger.error(f"Error disposing batch {batch.id}: {str(e)}")
            return False

    def process_batch_completion(self, batch_id: int) -> Dict[str, Any]:
        """
        Process batch completion - credit ingredients back to inventory if batch fails
        """
        try:
            batch = Batch.scoped().filter_by(id=batch_id).first()
            if not batch:
                return {'success': False, 'error': 'Batch not found'}

            if batch.status == 'completed':
                return {'success': True, 'message': 'Batch already completed'}

            # Process based on batch status
            if batch.status == 'failed' or batch.status == 'cancelled':
                return self._credit_ingredients_back(batch)
            else:
                # Mark as completed
                batch.status = 'completed'
                db.session.commit()
                return {'success': True, 'message': 'Batch marked as completed'}

        except Exception as e:
            logger.error(f"Error processing batch completion: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def get_batch_containers_summary(self, batch_id: int) -> Dict[str, Any]:
        """Get comprehensive container summary for a batch"""
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
            product_capacity = 0

            # Process regular containers
            for container in containers:
                container_info = {
                    'id': container.id,
                    'name': container.container.name if container.container else 'Unknown',
                    'quantity': container.quantity_used,
                    'reason': 'primary_packaging',
                    'one_time_use': False,
                    'exclude_from_product': False,
                    'capacity': (container.container.storage_amount or 0) * container.quantity_used,
                    'type': 'regular'
                }
                container_data.append(container_info)
                total_capacity += container_info['capacity']
                product_capacity += container_info['capacity']

            # Process extra containers
            for extra_container in extra_containers:
                container_info = {
                    'id': extra_container.id,
                    'name': extra_container.container.name if extra_container.container else 'Unknown',
                    'quantity': extra_container.quantity_used,
                    'reason': extra_container.reason,
                    'one_time_use': True,
                    'exclude_from_product': True,
                    'capacity': (extra_container.container.storage_amount or 0) * extra_container.quantity_used,
                    'type': 'extra'
                }
                container_data.append(container_info)
                total_capacity += container_info['capacity']

            summary = {
                'total_containers': len(container_data),
                'total_capacity': total_capacity,
                'product_containers': len([c for c in container_data if not c['exclude_from_product']]),
                'product_capacity': product_capacity,
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
        """Remove a container from a batch and restore inventory"""
        try:
            # Check if it's a regular container
            container = BatchContainer.query.filter_by(
                id=container_id,
                batch_id=batch_id,
                organization_id=current_user.organization_id
            ).first()

            if not container:
                # Check if it's an extra container
                container = ExtraBatchContainer.query.filter_by(
                    id=container_id,
                    batch_id=batch_id,
                    organization_id=current_user.organization_id
                ).first()

            if not container:
                return {'success': False, 'error': 'Container not found'}

            # Restore inventory if not one-time use
            if not getattr(container, 'one_time_use', False):
                process_inventory_adjustment(
                    inventory_item_id=container.container_id,
                    quantity_delta=container.quantity_used,  # Positive to restore
                    adjustment_type='batch_correction',
                    reason=f"Restored container from batch {batch_id}",
                    user_id=current_user.id,
                    organization_id=current_user.organization_id,
                    batch_id=batch_id
                )

            db.session.delete(container)
            db.session.commit()

            return {'success': True, 'message': 'Container removed successfully'}

        except Exception as e:
            logger.error(f"Error removing container: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def adjust_batch_container(self, batch_id: int, container_id: int,
                              adjustment_type: str, adjustment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust container quantity, replace container type, or mark as damaged"""
        try:
            batch = Batch.scoped().filter_by(id=batch_id).first()
            if not batch:
                return {'success': False, 'error': 'Batch not found'}

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

            notes = adjustment_data.get('notes', '')

            if adjustment_type == 'quantity':
                return self._adjust_container_quantity(container_record, batch, adjustment_data, notes)
            elif adjustment_type == 'replace':
                return self._replace_container(container_record, batch, adjustment_data, notes)
            elif adjustment_type == 'damage':
                return self._mark_container_damaged(container_record, batch, adjustment_data, notes)
            else:
                return {'success': False, 'error': 'Invalid adjustment type'}

        except Exception as e:
            logger.error(f"Error adjusting container: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def _adjust_container_quantity(self, container_record, batch, data, notes):
        """Adjust container quantity"""
        new_total = data.get('new_total_quantity', 0)
        if new_total < 0:
            return {'success': False, 'error': 'Total quantity cannot be negative'}

        current_qty = container_record.quantity_used
        quantity_difference = new_total - current_qty

        if quantity_difference != 0:
            # Adjust inventory
            change_type = 'refunded' if quantity_difference > 0 else 'batch_adjustment'
            process_inventory_adjustment(
                inventory_item_id=container_record.container_id,
                quantity_delta=quantity_difference,
                adjustment_type=change_type,
                reason=f"Container quantity adjustment for batch {batch.label_code}: {notes}",
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                batch_id=batch.id
            )

        container_record.quantity_used = new_total
        db.session.commit()
        return {'success': True, 'message': 'Container quantity adjusted'}

    def _replace_container(self, container_record, batch, data, notes):
        """Replace container with different type"""
        new_container_id = data.get('new_container_id')
        new_quantity = data.get('new_quantity', 1)

        if not new_container_id:
            return {'success': False, 'error': 'New container must be selected'}

        # Return old containers
        process_inventory_adjustment(
            inventory_item_id=container_record.container_id,
            quantity_delta=container_record.quantity_used,
            adjustment_type='refunded',
            reason=f"Container replacement return for batch {batch.label_code}: {notes}",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            batch_id=batch.id
        )

        # Deduct new containers
        new_container = InventoryItem.query.get_or_404(new_container_id)
        process_inventory_adjustment(
            inventory_item_id=new_container_id,
            quantity_delta=-new_quantity,
            adjustment_type='batch',
            reason=f"Container replacement for batch {batch.label_code}: {notes}",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            batch_id=batch.id
        )

        # Update container record
        container_record.container_id = new_container_id
        container_record.quantity_used = new_quantity
        container_record.cost_each = new_container.cost_per_unit or 0.0

        db.session.commit()
        return {'success': True, 'message': 'Container replaced successfully'}

    def _mark_container_damaged(self, container_record, batch, data, notes):
        """Mark containers as damaged and add replacements"""
        damage_quantity = data.get('damage_quantity', 0)
        if damage_quantity <= 0 or damage_quantity > container_record.quantity_used:
            return {'success': False, 'error': 'Invalid damage quantity'}

        # Check stock availability
        container_item = InventoryItem.query.get(container_record.container_id)
        if container_item.quantity < damage_quantity:
            return {
                'success': False,
                'error': f'Not enough {container_item.name} in stock to replace damaged containers. Available: {container_item.quantity}, Need: {damage_quantity}'
            }

        # Create extra container record for damaged units
        damaged_record = ExtraBatchContainer(
            batch_id=batch.id,
            container_id=container_record.container_id,
            container_quantity=damage_quantity,
            quantity_used=damage_quantity,
            cost_each=container_record.cost_each,
            reason='damaged',
            organization_id=current_user.organization_id
        )
        db.session.add(damaged_record)

        # Deduct replacement containers
        process_inventory_adjustment(
            inventory_item_id=container_record.container_id,
            quantity_delta=-damage_quantity,
            adjustment_type='damaged',
            reason=f"Replacement containers for damaged units in batch {batch.label_code}: {notes}",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            batch_id=batch.id
        )

        db.session.commit()
        return {'success': True, 'message': 'Damaged containers marked and replacements deducted'}

    def _credit_ingredients_back(self, batch: Batch) -> Dict[str, Any]:
        """Helper to credit ingredients back to inventory for failed/cancelled batches"""
        ingredients_to_credit = BatchIngredient.query.filter_by(batch_id=batch.id).all()
        success = True
        for ingredient in ingredients_to_credit:
            result = process_inventory_adjustment(
                inventory_item_id=ingredient.ingredient_id,
                quantity_delta=ingredient.quantity_consumed,
                adjustment_type='batch_reversal',
                reason=f"Reverting consumption for failed batch {batch.batch_number}",
                user_id=batch.created_by,
                organization_id=batch.organization_id,
                batch_id=batch.id
            )
            if not result['success']:
                logger.error(f"Failed to credit ingredient {ingredient.ingredient_id} back for batch {batch.id}: {result.get('error')}")
                success = False
        
        if success:
            batch.status = batch.status # Keep failed/cancelled status but mark as processed for credit
            db.session.commit()
            return {'success': True, 'message': 'Ingredients credited back to inventory'}
        else:
            return {'success': False, 'error': 'Failed to credit all ingredients back'}