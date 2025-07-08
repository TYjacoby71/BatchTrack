
"""
Shopify webhook routes for inventory integration
Uses the FIFOService for all inventory operations
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.extensions import db
from app.models import InventoryItem
from app.models.product import ProductSKU
from app.blueprints.fifo.services import FIFOService
import hmac
import hashlib
import os

shopify_bp = Blueprint('shopify', __name__, url_prefix='/webhook/shopify')

def verify_webhook(data, signature):
    """Verify Shopify webhook signature"""
    webhook_secret = os.environ.get('SHOPIFY_WEBHOOK_SECRET')
    if not webhook_secret:
        return False
    
    computed_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, signature)

@shopify_bp.route('/order/created', methods=['POST'])
def handle_order_created():
    """Handle Shopify order creation - reserve inventory"""
    # Verify webhook signature
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    if not verify_webhook(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    
    try:
        for line_item in data.get('line_items', []):
            sku = line_item.get('sku')
            quantity = line_item.get('quantity', 0)
            
            # Find the product SKU
            product_sku = ProductSKU.query.filter_by(sku_code=sku).first()
            if not product_sku:
                continue
            
            # Reserve inventory using FIFO
            deduction_plan = FIFOService.calculate_deduction_plan(
                product_sku.inventory_item_id, quantity
            )
            
            if deduction_plan:
                FIFOService.execute_deduction_plan(
                    product_sku.inventory_item_id,
                    deduction_plan,
                    'reserved',
                    f"Shopify order #{data.get('order_number')}",
                    order_id=str(data.get('id')),
                    customer=data.get('customer', {}).get('email'),
                    sale_price=float(line_item.get('price', 0))
                )
        
        db.session.commit()
        return jsonify({'status': 'success'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@shopify_bp.route('/order/paid', methods=['POST'])
def handle_order_paid():
    """Handle Shopify order payment - convert reservations to sales"""
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    if not verify_webhook(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    order_id = str(data.get('id'))
    
    try:
        for line_item in data.get('line_items', []):
            sku = line_item.get('sku')
            quantity = line_item.get('quantity', 0)
            
            product_sku = ProductSKU.query.filter_by(sku_code=sku).first()
            if not product_sku:
                continue
            
            # Convert reservation to sale
            FIFOService.convert_reservation_to_sale(
                product_sku.inventory_item_id,
                quantity,
                order_id,
                f"Shopify order #{data.get('order_number')} paid"
            )
        
        db.session.commit()
        return jsonify({'status': 'success'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@shopify_bp.route('/order/cancelled', methods=['POST'])
def handle_order_cancelled():
    """Handle Shopify order cancellation - release reservations"""
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    if not verify_webhook(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    order_id = str(data.get('id'))
    
    try:
        for line_item in data.get('line_items', []):
            sku = line_item.get('sku')
            quantity = line_item.get('quantity', 0)
            
            product_sku = ProductSKU.query.filter_by(sku_code=sku).first()
            if not product_sku:
                continue
            
            # Release reservation
            FIFOService.release_reservation(
                product_sku.inventory_item_id,
                quantity,
                order_id,
                f"Shopify order #{data.get('order_number')} cancelled"
            )
        
        db.session.commit()
        return jsonify({'status': 'success'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@shopify_bp.route('/refund/create', methods=['POST'])
def handle_refund_created():
    """Handle Shopify refund - credit inventory back"""
    signature = request.headers.get('X-Shopify-Hmac-Sha256')
    if not verify_webhook(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    order_id = str(data.get('order_id'))
    
    try:
        for refund_line_item in data.get('refund_line_items', []):
            line_item = refund_line_item.get('line_item', {})
            sku = line_item.get('sku')
            quantity = refund_line_item.get('quantity', 0)
            
            product_sku = ProductSKU.query.filter_by(sku_code=sku).first()
            if not product_sku:
                continue
            
            # Credit inventory back using FIFO
            FIFOService.handle_refund_credits(
                product_sku.inventory_item_id,
                quantity,
                'returned',
                f"Shopify refund for order #{order_id}",
                order_id=order_id,
                sale_price=float(line_item.get('price', 0))
            )
        
        db.session.commit()
        return jsonify({'status': 'success'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
