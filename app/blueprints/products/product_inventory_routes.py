
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Batch
from ...services.product_service import ProductService
from ...services.inventory_adjustment import process_inventory_adjustment

product_inventory_bp = Blueprint('product_inventory', __name__, url_prefix='/products/inventory')

@product_inventory_bp.route('/add-from-batch', methods=['POST'])
@login_required
def add_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()
    
    batch_id = data.get('batch_id')
    product_id = data.get('product_id')
    variant_label = data.get('variant_label')
    quantity = data.get('quantity')
    container_overrides = data.get('container_overrides', {})
    
    if not batch_id or not product_id:
        return jsonify({'error': 'Batch ID and Product ID are required'}), 400
    
    try:
        batch = Batch.query.get(batch_id)
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
            
        target_sku = ProductSKU.query.get(product_id)
        if not target_sku:
            return jsonify({'error': 'Target SKU not found'}), 404
        
        inventory_entries = []
        total_containerized = 0
        
        # Process regular containers
        for container in batch.containers:
            final_quantity = container_overrides.get(str(container.container_id), container.quantity_used)
            if final_quantity > 0:
                container_capacity = (container.container.storage_amount or 1) * final_quantity
                total_containerized += container_capacity
                
                # Create container size label
                container_size_label = f"{container.container.storage_amount or 1}{container.container.storage_unit or 'count'} {container.container.name}"
                
                # Get or create SKU for this container size
                container_sku = ProductService.get_or_create_sku(
                    product_name=target_sku.product_name,
                    variant_name=variant_label,
                    size_label=container_size_label,
                    unit=batch.output_unit or target_sku.unit
                )
                
                # Add inventory using centralized service
                total_container_volume = container_capacity
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
            final_quantity = container_overrides.get(str(extra_container.container_id), extra_container.quantity_used)
            if final_quantity > 0:
                container_capacity = (extra_container.container.storage_amount or 1) * final_quantity
                total_containerized += container_capacity
                
                # Create container size label
                container_size_label = f"{extra_container.container.storage_amount or 1}{extra_container.container.storage_unit or 'count'} {extra_container.container.name}"
                
                # Get or create SKU for this container size
                container_sku = ProductService.get_or_create_sku(
                    product_name=target_sku.product_name,
                    variant_name=variant_label,
                    size_label=container_size_label,
                    unit=batch.output_unit or target_sku.unit
                )
                
                # Add inventory using centralized service
                total_container_volume = container_capacity
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
            # Add to bulk SKU
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
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'inventory_entries': inventory_entries,
            'message': f'Successfully added product inventory from batch {batch.label_code}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
