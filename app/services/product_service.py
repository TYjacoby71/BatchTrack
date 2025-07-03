from sqlalchemy import func
from ..models import db, ProductSKU, ProductSKUHistory
from datetime import datetime
from typing import Optional, Dict, List, Tuple

class ProductService:
    @staticmethod
    def get_product_summary_skus():
        """Get summary of all products with their total quantities"""
        # Group by product_name and aggregate quantities
        product_summaries = db.session.query(
            ProductSKU.product_name,
            ProductSKU.unit,
            func.sum(ProductSKU.current_quantity).label('total_quantity'),
            func.count(ProductSKU.id).label('sku_count'),
            func.min(ProductSKU.low_stock_threshold).label('low_stock_threshold'),
            func.max(ProductSKU.updated_at).label('last_updated')
        ).filter(
            ProductSKU.is_active == True,
            ProductSKU.is_product_active == True
        ).group_by(
            ProductSKU.product_name,
            ProductSKU.unit
        ).all()

        products = []
        for summary in product_summaries:
            products.append({
                'product_name': summary.product_name,
                'product_base_unit': summary.unit,
                'total_quantity': float(summary.total_quantity or 0),
                'sku_count': summary.sku_count,
                'low_stock_threshold': float(summary.low_stock_threshold or 0),
                'last_updated': summary.last_updated
            })

        return products

    @staticmethod
    def get_or_create_sku(product_name, variant_name, size_label, unit=None, sku_code=None, variant_description=None):
        """Get existing SKU or create new one with automatic SKU generation"""
        # Check if SKU already exists
        sku = ProductSKU.query.filter_by(
            product_name=product_name,
            variant_name=variant_name,
            size_label=size_label
        ).first()

        if sku:
            # If SKU exists but doesn't have a code, generate one
            if not sku.sku_code or sku.sku_code.strip() == '':
                sku.sku_code = ProductService.generate_sku_code(product_name, variant_name, size_label)
                db.session.flush()
            return sku

        # Always generate SKU code automatically
        if not sku_code:
            sku_code = ProductService.generate_sku_code(product_name, variant_name, size_label)

        # Get product base unit from existing SKUs
        existing_sku = ProductSKU.query.filter_by(product_name=product_name).first()
        product_base_unit = existing_sku.unit if existing_sku else (unit or 'g')

        # Create new SKU
        sku = ProductSKU(
            product_name=product_name,
            variant_name=variant_name,
            size_label=size_label,
            unit=unit or product_base_unit,
            sku_code=sku_code
        )

        db.session.add(sku)
        db.session.flush()
        return sku

    @staticmethod
    def ensure_base_variant_if_needed(product_name):
        """Create a Base variant if no variants exist for a product"""
        existing_skus = ProductSKU.query.filter_by(
            product_name=product_name,
            is_active=True
        ).all()

        if not existing_skus:
            # No variants exist, create a Base variant
            base_sku = ProductService.get_or_create_sku(
                product_name=product_name,
                variant_name='Base',
                size_label='Bulk'
            )
            return base_sku
        return None

    @staticmethod
    def backfill_missing_sku_codes():
        """Generate SKU codes for any SKUs that don't have them"""
        skus_without_codes = ProductSKU.query.filter(
            ProductSKU.sku_code.is_(None),
            ProductSKU.is_active == True
        ).all()

        for sku in skus_without_codes:
            sku.sku_code = ProductService.generate_sku_code(
                sku.product_name, 
                sku.variant_name, 
                sku.size_label
            )

        if skus_without_codes:
            db.session.commit()
            return len(skus_without_codes)
        return 0

    @staticmethod
    def generate_sku_code(product_name, variant_name, size_label):
        """Generate a unique SKU code based on product components"""
        # Create base SKU from first 3 characters of each component
        product_part = ''.join(c for c in product_name[:3].upper() if c.isalnum())
        variant_part = ''.join(c for c in variant_name[:2].upper() if c.isalnum())  
        size_part = ''.join(c for c in size_label[:3].upper() if c.isalnum())

        # Ensure we have at least some characters from each part
        product_part = product_part[:3].ljust(2, 'X')
        variant_part = variant_part[:2].ljust(2, 'X')
        size_part = size_part[:3].ljust(2, 'X')

        base_sku = f"{product_part}-{variant_part}-{size_part}"

        # Check for uniqueness by querying for existing SKUs with the same base
        count = 1
        unique_sku_code = base_sku
        while ProductSKU.query.filter(ProductSKU.sku_code == unique_sku_code).first():
            unique_sku_code = f"{base_sku}-{count}"
            count += 1

        return unique_sku_code

    @staticmethod
    def get_fifo_inventory_groups(product_name):
        """Get FIFO inventory groups for a product (legacy compatibility)"""
        # Get all SKUs for the product
        skus = ProductSKU.query.filter_by(
            product_name=product_name,
            is_active=True
        ).filter(ProductSKU.current_quantity > 0).all()

        groups = []
        for sku in skus:
            groups.append({
                'sku_id': sku.id,
                'variant_name': sku.variant_name,
                'size_label': sku.size_label,
                'quantity': sku.current_quantity,
                'unit': sku.unit,
                'unit_cost': sku.unit_cost,
                'expiration_date': sku.expiration_date,
                'fifo_id': sku.fifo_id
            })

        return groups

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
    def get_products_summary():
        return ProductService.get_product_summary_skus()

    @staticmethod
    def get_low_stock_skus(threshold_multiplier: float = 1.0):
        """Get SKUs that are low on stock"""
        return ProductSKU.query.filter(
            ProductSKU.current_quantity <= ProductSKU.low_stock_threshold * threshold_multiplier,
            ProductSKU.is_active == True
        ).all()

    @staticmethod
    def add_product_from_batch(batch_id, product_id, variant_label, quantity, container_overrides=None):
        """
        Add product inventory from a completed batch using centralized inventory adjustment service
        
        Args:
            batch_id: The batch ID
            product_id: The SKU ID to add inventory to
            variant_label: The variant name 
            quantity: Total yield quantity
            container_overrides: Dict of container_id -> final_quantity for containers going to products
        
        Returns:
            List of inventory entries created
        """
        from app.models import Batch, ProductSKU
        from app.services.inventory_adjustment import process_inventory_adjustment
        from flask_login import current_user
        
        batch = Batch.query.get(batch_id)
        if not batch:
            raise ValueError("Batch not found")
            
        target_sku = ProductSKU.query.get(product_id)
        if not target_sku:
            raise ValueError("Target SKU not found")
        
        container_overrides = container_overrides or {}
        inventory_entries = []
        
        # Calculate total container capacity being used for products
        total_containerized = 0
        
        # Process regular containers
        for container in batch.containers:
            final_quantity = container_overrides.get(container.container_id, container.quantity_used)
            if final_quantity > 0:
                container_capacity = (container.container.storage_amount or 1) * final_quantity
                total_containerized += container_capacity
                
                # Create individual SKUs for each container
                container_size_label = f"{container.container.storage_amount or 1}{container.container.storage_unit or 'count'} {container.container.name}"
                
                # Get or create SKU for this container size
                container_sku = ProductService.get_or_create_sku(
                    product_name=target_sku.product_name,
                    variant_name=variant_label,
                    size_label=container_size_label,
                    unit=batch.output_unit or target_sku.unit
                )
                
                # Add inventory for each container count using centralized service
                container_fill = container.container.storage_amount or 1
                total_container_volume = container_fill * final_quantity
                
                success = process_inventory_adjustment(
                    item_id=container_sku.id,
                    quantity=total_container_volume,
                    change_type='finished_batch',
                    unit=batch.output_unit or target_sku.unit,
                    notes=f"From batch {batch.label_code} - {final_quantity} containers",
                    batch_id=batch_id,
                    created_by=current_user.id,
                    item_type='sku',
                    custom_expiration_date=batch.expiration_date,
                    custom_shelf_life_days=batch.shelf_life_days
                )
                
                if success:
                    inventory_entries.append({
                        'sku_id': container_sku.id,
                        'quantity': total_container_volume,
                        'container_name': container.container.name,
                        'container_count': final_quantity,
                        'type': 'container'
                    })
        
        # Process extra containers  
        for extra_container in batch.extra_containers:
            final_quantity = container_overrides.get(extra_container.container_id, extra_container.quantity_used)
            if final_quantity > 0:
                container_capacity = (extra_container.container.storage_amount or 1) * final_quantity
                total_containerized += container_capacity
                
                # Create individual SKUs for each extra container
                container_size_label = f"{extra_container.container.storage_amount or 1}{extra_container.container.storage_unit or 'count'} {extra_container.container.name}"
                
                # Get or create SKU for this container size
                container_sku = ProductService.get_or_create_sku(
                    product_name=target_sku.product_name,
                    variant_name=variant_label,
                    size_label=container_size_label,
                    unit=batch.output_unit or target_sku.unit
                )
                
                # Add inventory for each container count using centralized service
                container_fill = extra_container.container.storage_amount or 1
                total_container_volume = container_fill * final_quantity
                
                success = process_inventory_adjustment(
                    item_id=container_sku.id,
                    quantity=total_container_volume,
                    change_type='finished_batch',
                    unit=batch.output_unit or target_sku.unit,
                    notes=f"From batch {batch.label_code} - {final_quantity} extra containers",
                    batch_id=batch_id,
                    created_by=current_user.id,
                    item_type='sku',
                    custom_expiration_date=batch.expiration_date,
                    custom_shelf_life_days=batch.shelf_life_days
                )
                
                if success:
                    inventory_entries.append({
                        'sku_id': container_sku.id,
                        'quantity': total_container_volume,
                        'container_name': extra_container.container.name,
                        'container_count': final_quantity,
                        'type': 'extra_container'
                    })
        
        # Handle remaining bulk quantity
        bulk_quantity = quantity - total_containerized
        if bulk_quantity > 0:
            # Add to bulk SKU (existing target SKU or create bulk variant)
            bulk_sku = target_sku
            if target_sku.size_label != 'Bulk':
                # Get or create bulk SKU for this product/variant
                bulk_sku = ProductService.get_or_create_sku(
                    product_name=target_sku.product_name,
                    variant_name=variant_label,
                    size_label='Bulk',
                    unit=batch.output_unit or target_sku.unit
                )
            
            success = process_inventory_adjustment(
                item_id=bulk_sku.id,
                quantity=bulk_quantity,
                change_type='finished_batch',
                unit=batch.output_unit or target_sku.unit,
                notes=f"From batch {batch.label_code} - Bulk remainder",
                batch_id=batch_id,
                created_by=current_user.id,
                item_type='sku',
                custom_expiration_date=batch.expiration_date,
                custom_shelf_life_days=batch.shelf_life_days
            )
            
            if success:
                inventory_entries.append({
                    'sku_id': bulk_sku.id,
                    'quantity': bulk_quantity,
                    'type': 'bulk'
                })
        
        return inventory_entries