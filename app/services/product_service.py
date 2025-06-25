from sqlalchemy import func
from ..models import db, ProductSKU, ProductSKUHistory, Batch
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from flask_login import current_user

class ProductService:
    """Unified service for all product operations using single ProductSKU table"""

    @staticmethod
    def create_product_sku(product_name: str, variant_name: str = 'Base', size_label: str = 'Bulk', 
                          unit: str = 'count', product_base_unit: str = 'count', 
                          initial_quantity: float = 0, unit_cost: float = 0,
                          container_id: Optional[int] = None, batch_id: Optional[int] = None,
                          notes: str = '') -> ProductSKU:
        """Create a new ProductSKU entry"""

        sku = ProductSKU(
            product_name=product_name,
            product_base_unit=product_base_unit,
            variant_name=variant_name,
            size_label=size_label,
            unit=unit,
            current_quantity=initial_quantity,
            unit_cost=unit_cost,
            container_id=container_id,
            batch_id=batch_id,
            notes=notes,
            created_by=current_user.id if current_user.is_authenticated else None,
            organization_id=current_user.organization_id if current_user.is_authenticated else None
        )

        db.session.add(sku)
        db.session.flush()  # Get the ID

        # Create history entry for initial stock
        if initial_quantity > 0:
            history = ProductSKUHistory(
                sku_id=sku.id,
                change_type='initial_stock',
                quantity_change=initial_quantity,
                old_quantity=0,
                new_quantity=initial_quantity,
                unit_cost=unit_cost,
                batch_id=batch_id,
                notes=f"Initial stock: {notes}",
                created_by=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(history)

        return sku

    @staticmethod
    def adjust_sku_quantity(sku_id: int, quantity_change: float, change_type: str,
                           unit_cost: Optional[float] = None, sale_price: Optional[float] = None,
                           customer: Optional[str] = None, notes: str = '',
                           batch_id: Optional[int] = None) -> bool:
        """Adjust SKU quantity and create history entry"""

        sku = ProductSKU.query.get_or_404(sku_id)
        old_quantity = sku.current_quantity

        # For recount, quantity_change is the new total
        if change_type == 'recount':
            new_quantity = quantity_change
            actual_change = new_quantity - old_quantity
        else:
            new_quantity = old_quantity + quantity_change
            actual_change = quantity_change

        # Validate quantity doesn't go negative (except for recount)
        if new_quantity < 0 and change_type != 'recount':
            return False

        # Update SKU quantity
        sku.current_quantity = max(0, new_quantity)
        sku.last_updated = datetime.utcnow()

        # Create history entry
        history = ProductSKUHistory(
            sku_id=sku_id,
            change_type=change_type,
            quantity_change=actual_change,
            old_quantity=old_quantity,
            new_quantity=sku.current_quantity,
            unit_cost=unit_cost,
            sale_price=sale_price,
            customer=customer,
            batch_id=batch_id,
            notes=notes,
            created_by=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(history)

        db.session.commit()
        return True

    @staticmethod
    def add_from_batch(batch_id: int, product_name: str, variant_name: str = 'Base',
                      size_label: str = 'Bulk', quantity: float = 0,
                      container_overrides: Optional[Dict[int, int]] = None) -> List[ProductSKU]:
        """Add product inventory from a finished batch"""
        from ..models import BatchContainer, InventoryItem

        batch = Batch.query.get_or_404(batch_id)
        skus_created = []

        # Get containers used in this batch
        batch_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()

        if batch_containers:
            # Create separate SKUs for each container type
            for container_usage in batch_containers:
                container = container_usage.container
                container_size_label = f"{container.storage_amount} {container.storage_unit} {container.name.replace('Container - ', '')}"

                # Use override count if provided
                final_count = container_usage.quantity_used
                if container_overrides and container.id in container_overrides:
                    final_count = container_overrides[container.id]

                # Calculate cost per unit
                batch_cost_per_unit = 0
                if batch.total_cost and batch.final_quantity:
                    batch_cost_per_unit = batch.total_cost / batch.final_quantity

                sku = ProductService.create_product_sku(
                    product_name=product_name,
                    variant_name=variant_name,
                    size_label=container_size_label,
                    unit='count',
                    product_base_unit=batch.output_unit or 'count',
                    initial_quantity=final_count,
                    unit_cost=batch_cost_per_unit,
                    container_id=container.id,
                    batch_id=batch_id,
                    notes=f"From batch #{batch.id} - {container.name}"
                )
                skus_created.append(sku)
        else:
            # Create bulk SKU for non-containerized batches
            batch_unit = batch.output_unit or batch.projected_yield_unit or 'oz'
            quantity_used = quantity or batch.final_quantity or batch.projected_yield

            batch_cost_per_unit = 0
            if batch.total_cost and batch.final_quantity:
                batch_cost_per_unit = batch.total_cost / batch.final_quantity

            sku = ProductService.create_product_sku(
                product_name=product_name,
                variant_name=variant_name,
                size_label=size_label,
                unit=batch_unit,
                product_base_unit=batch_unit,
                initial_quantity=quantity_used,
                unit_cost=batch_cost_per_unit,
                batch_id=batch_id,
                notes=f"Bulk from batch #{batch.id}"
            )
            skus_created.append(sku)

        db.session.commit()
        return skus_created

    @staticmethod
    def get_product_summary():
        """Get summary of all products grouped by product_name"""
        results = db.session.query(
            ProductSKU.product_name,
            func.count(ProductSKU.id).label('sku_count'),
            func.sum(ProductSKU.current_quantity).label('total_quantity'),
            func.min(ProductSKU.low_stock_threshold).label('min_threshold'),
            func.max(ProductSKU.is_product_active).label('is_active')
        ).filter(
            ProductSKU.is_active == True
        ).group_by(
            ProductSKU.product_name
        ).order_by(
            ProductSKU.product_name
        ).all()

        return results

    @staticmethod
    def get_skus_by_product(product_name: str):
        """Get all SKUs for a specific product"""
        return ProductSKU.query.filter_by(
            product_name=product_name,
            is_active=True
        ).order_by(
            ProductSKU.variant_name,
            ProductSKU.size_label
        ).all()

    @staticmethod
    def get_low_stock_skus():
        """Get SKUs that are low on stock"""
        return ProductSKU.query.filter(
            ProductSKU.is_active == True,
            ProductSKU.current_quantity <= ProductSKU.low_stock_threshold
        ).order_by(
            ProductSKU.product_name,
            ProductSKU.variant_name
        ).all()

    @staticmethod
    def search_skus(search_term: str):
        """Search SKUs by product name, variant, or size label"""
        search_pattern = f"%{search_term}%"
        return ProductSKU.query.filter(
            db.or_(
                ProductSKU.product_name.ilike(search_pattern),
                ProductSKU.variant_name.ilike(search_pattern),
                ProductSKU.size_label.ilike(search_pattern),
                ProductSKU.sku_code.ilike(search_pattern)
            ),
            ProductSKU.is_active == True
        ).order_by(
            ProductSKU.product_name,
            ProductSKU.variant_name
        ).all()

    @staticmethod
    def delete_sku(sku_id: int) -> bool:
        """Delete a SKU and its history"""
        try:
            sku = ProductSKU.query.get_or_404(sku_id)

            # Check if SKU has any batches associated
            if sku.batch_id:
                return False  # Cannot delete if tied to batches

            # Delete history entries
            ProductSKUHistory.query.filter_by(sku_id=sku_id).delete()

            # Delete the SKU
            db.session.delete(sku)
            db.session.commit()
            return True

        except Exception:
            db.session.rollback()
            return False