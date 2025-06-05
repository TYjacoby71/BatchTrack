
from flask import Blueprint, jsonify, request
from flask_login import login_required
from models import db, Product, ProductVariation, ProductInventory, ProductEvent
from services.product_inventory_service import ProductInventoryService
from datetime import datetime

marketplace_api_bp = Blueprint('marketplace_api', __name__, url_prefix='/api/marketplace')

@marketplace_api_bp.route('/products', methods=['GET'])
@login_required
def get_products_catalog():
    """Get product catalog for marketplace sync"""
    products = ProductInventoryService.get_product_summary()
    
    catalog = []
    for product in products:
        product_data = {
            'id': product.id,
            'name': product.name,
            'base_unit': product.product_base_unit,
            'bulk_inventory': getattr(product, 'bulk_inventory', 0),
            'packaged_inventory': getattr(product, 'packaged_inventory', 0),
            'total_cost': getattr(product, 'total_cost', 0),
            'total_value': getattr(product, 'total_value', 0),
            'low_stock_threshold': product.low_stock_threshold,
            'is_active': product.is_active,
            'created_at': product.created_at.isoformat(),
            'variants': []
        }
        
        for variation in product.variations:
            # Calculate variant inventory
            variation_inventory = [inv for inv in product.inventory if inv.variant == variation.name]
            bulk_qty = sum(inv.quantity for inv in variation_inventory if inv.size_label == 'Bulk' and inv.quantity > 0)
            packaged_qty = sum(inv.quantity for inv in variation_inventory if inv.size_label != 'Bulk' and inv.quantity > 0)
            
            variant_data = {
                'id': variation.id,
                'name': variation.name,
                'sku': variation.sku,
                'description': variation.description,
                'retail_price': variation.retail_price or 0,
                'wholesale_price': variation.wholesale_price or 0,
                'is_active': variation.is_active,
                'marketplace_id': variation.marketplace_id,
                'bulk_quantity': bulk_qty,
                'packaged_quantity': packaged_qty,
                'total_quantity': bulk_qty + packaged_qty,
                'sizes': []
            }
            
            # Get unique sizes for this variant
            sizes = set()
            for inv in variation_inventory:
                if inv.quantity > 0:
                    sizes.add((inv.size_label, inv.unit))
            
            for size_label, unit in sizes:
                size_inventory = [inv for inv in variation_inventory if inv.size_label == size_label and inv.unit == unit]
                total_qty = sum(inv.quantity for inv in size_inventory)
                
                variant_data['sizes'].append({
                    'size_label': size_label,
                    'unit': unit,
                    'quantity': total_qty
                })
            
            product_data['variants'].append(variant_data)
        
        catalog.append(product_data)
    
    return jsonify({
        'success': True,
        'products': catalog,
        'total_count': len(catalog)
    })

@marketplace_api_bp.route('/inventory/<sku>', methods=['GET'])
@login_required
def get_sku_inventory(sku):
    """Get real-time inventory for a specific SKU"""
    variation = ProductVariation.query.filter_by(sku=sku).first()
    
    if not variation:
        return jsonify({'error': 'SKU not found'}), 404
    
    # Get inventory for this variation
    inventory = ProductInventory.query.filter_by(
        product_id=variation.product_id,
        variant=variation.name
    ).filter(ProductInventory.quantity > 0).all()
    
    bulk_qty = sum(inv.quantity for inv in inventory if inv.size_label == 'Bulk')
    packaged_qty = sum(inv.quantity for inv in inventory if inv.size_label != 'Bulk')
    
    return jsonify({
        'success': True,
        'sku': sku,
        'variant_name': variation.name,
        'bulk_quantity': bulk_qty,
        'packaged_quantity': packaged_qty,
        'total_quantity': bulk_qty + packaged_qty,
        'retail_price': variation.retail_price or 0,
        'wholesale_price': variation.wholesale_price or 0,
        'is_active': variation.is_active,
        'last_updated': max([inv.timestamp for inv in inventory]).isoformat() if inventory else None
    })

@marketplace_api_bp.route('/orders/process', methods=['POST'])
@login_required
def process_order():
    """Process an order from marketplace (deduct inventory using FIFO)"""
    data = request.get_json()
    
    order_id = data.get('order_id')
    items = data.get('items', [])
    
    if not order_id or not items:
        return jsonify({'error': 'Order ID and items are required'}), 400
    
    results = []
    errors = []
    
    for item in items:
        sku = item.get('sku')
        quantity = item.get('quantity', 0)
        size_preference = item.get('size_preference', 'packaged')  # 'bulk' or 'packaged'
        
        if not sku or quantity <= 0:
            errors.append(f"Invalid item data: {item}")
            continue
        
        variation = ProductVariation.query.filter_by(sku=sku).first()
        if not variation:
            errors.append(f"SKU not found: {sku}")
            continue
        
        # Determine unit based on size preference
        unit = 'count' if size_preference == 'packaged' else variation.product.product_base_unit
        
        # Process deduction using FIFO
        success = ProductInventoryService.deduct_fifo(
            product_id=variation.product_id,
            variant_label=variation.name,
            unit=unit,
            quantity=quantity,
            reason='marketplace_sale',
            notes=f"Order #{order_id} - {sku}"
        )
        
        if success:
            results.append({
                'sku': sku,
                'quantity_deducted': quantity,
                'unit': unit,
                'status': 'success'
            })
        else:
            errors.append(f"Insufficient stock for SKU: {sku} (requested: {quantity})")
    
    return jsonify({
        'success': len(errors) == 0,
        'order_id': order_id,
        'processed_items': results,
        'errors': errors
    })

@marketplace_api_bp.route('/variants/<int:variation_id>/pricing', methods=['PUT'])
@login_required
def update_variant_pricing(variation_id):
    """Update pricing for a product variation"""
    data = request.get_json()
    
    variation = ProductVariation.query.get_or_404(variation_id)
    
    if 'retail_price' in data:
        variation.retail_price = float(data['retail_price'])
    
    if 'wholesale_price' in data:
        variation.wholesale_price = float(data['wholesale_price'])
    
    if 'is_active' in data:
        variation.is_active = bool(data['is_active'])
    
    if 'marketplace_id' in data:
        variation.marketplace_id = data['marketplace_id']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'variation': {
            'id': variation.id,
            'name': variation.name,
            'sku': variation.sku,
            'retail_price': variation.retail_price,
            'wholesale_price': variation.wholesale_price,
            'is_active': variation.is_active,
            'marketplace_id': variation.marketplace_id
        }
    })

@marketplace_api_bp.route('/sync-status', methods=['GET'])
@login_required
def get_sync_status():
    """Get synchronization status with marketplaces"""
    total_products = Product.query.filter_by(is_active=True).count()
    total_variants = ProductVariation.query.filter_by(is_active=True).count()
    variants_with_sku = ProductVariation.query.filter(
        ProductVariation.sku.isnot(None),
        ProductVariation.is_active == True
    ).count()
    variants_with_pricing = ProductVariation.query.filter(
        ProductVariation.retail_price > 0,
        ProductVariation.is_active == True
    ).count()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_products': total_products,
            'total_variants': total_variants,
            'variants_with_sku': variants_with_sku,
            'variants_with_pricing': variants_with_pricing,
            'sku_coverage': round((variants_with_sku / total_variants * 100), 2) if total_variants > 0 else 0,
            'pricing_coverage': round((variants_with_pricing / total_variants * 100), 2) if total_variants > 0 else 0
        }
    })
