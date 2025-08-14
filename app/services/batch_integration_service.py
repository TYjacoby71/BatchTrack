
from typing import Optional, Dict, Any
from ..services.inventory_adjustment import process_inventory_adjustment
from ..models import Batch, InventoryItem
from ..extensions import db
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
