
from flask import Blueprint, jsonify, request
from flask_login import login_required
from models import db, InventoryItem, InventoryHistory, Batch, BatchIngredient, ExtraBatchIngredient
from datetime import datetime, date
from utils.fifo_generator import int_to_base36

fifo_api_bp = Blueprint('fifo_api', __name__)

@fifo_api_bp.route('/api/fifo-details/<int:inventory_id>')
@login_required
def get_fifo_details(inventory_id):
    try:
        batch_id = request.args.get('batch_id', type=int)
        
        # Get inventory item
        item = InventoryItem.query.get_or_404(inventory_id)
        
        # Get current FIFO entries (available stock)
        fifo_entries = InventoryHistory.query.filter_by(inventory_item_id=inventory_id) \
            .filter(InventoryHistory.remaining_quantity > 0) \
            .order_by(InventoryHistory.timestamp.asc()).all()
        
        # Get batch usage if batch_id provided
        batch_usage = []
        if batch_id:
            batch_usage = get_batch_fifo_usage(inventory_id, batch_id)
        
        # Process FIFO entries
        fifo_data = []
        for entry in fifo_entries:
            age_days = None
            life_remaining_percent = None
            
            if entry.timestamp:
                age_days = (datetime.utcnow() - entry.timestamp).days
                
                if entry.is_perishable and entry.shelf_life_days:
                    life_remaining_percent = max(0, 100 - ((age_days / entry.shelf_life_days) * 100))
                    life_remaining_percent = round(life_remaining_percent, 1)
            
            fifo_data.append({
                'fifo_id': int_to_base36(entry.id),
                'remaining_quantity': entry.remaining_quantity,
                'unit': entry.unit,
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
                'age_days': age_days,
                'life_remaining_percent': life_remaining_percent,
                'unit_cost': entry.unit_cost
            })
        
        return jsonify({
            'inventory_item': {
                'name': item.name,
                'type': item.type,
                'quantity': item.quantity,
                'unit': item.unit
            },
            'fifo_entries': fifo_data,
            'batch_usage': batch_usage
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@fifo_api_bp.route('/api/batch-inventory-summary/<int:batch_id>')
@login_required
def get_batch_inventory_summary(batch_id):
    try:
        # Get batch
        batch = Batch.query.get_or_404(batch_id)
        
        # Get all ingredients used in this batch
        ingredient_summary = []
        
        # Regular batch ingredients
        batch_ingredients = BatchIngredient.query.filter_by(batch_id=batch_id).all()
        for batch_ing in batch_ingredients:
            usage_data = get_batch_fifo_usage(batch_ing.ingredient_id, batch_id)
            total_used = sum(usage['quantity_used'] for usage in usage_data)
            
            ingredient_summary.append({
                'name': batch_ing.ingredient.name,
                'total_used': total_used,
                'unit': batch_ing.unit,
                'fifo_usage': usage_data
            })
        
        # Extra ingredients
        extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch_id).all()
        for extra_ing in extra_ingredients:
            usage_data = get_batch_fifo_usage(extra_ing.ingredient_id, batch_id)
            total_used = sum(usage['quantity_used'] for usage in usage_data)
            
            ingredient_summary.append({
                'name': extra_ing.ingredient.name,
                'total_used': total_used,
                'unit': extra_ing.unit,
                'fifo_usage': usage_data
            })
        
        return jsonify({
            'batch': {
                'label_code': batch.label_code,
                'recipe_name': batch.recipe.name,
                'scale': batch.scale
            },
            'ingredient_summary': ingredient_summary
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_batch_fifo_usage(inventory_id, batch_id):
    """Get FIFO usage data for a specific ingredient in a specific batch"""
    # Get deduction history entries for this batch
    deduction_entries = InventoryHistory.query.filter_by(
        inventory_item_id=inventory_id
    ).filter(
        InventoryHistory.batch_id == batch_id,
        InventoryHistory.change_type.in_(['use', 'batch_use'])
    ).all()
    
    usage_data = []
    for entry in deduction_entries:
        age_days = None
        life_remaining_percent = None
        
        if entry.timestamp:
            age_days = (datetime.utcnow() - entry.timestamp).days
            
            if entry.is_perishable and entry.shelf_life_days:
                life_remaining_percent = max(0, 100 - ((age_days / entry.shelf_life_days) * 100))
                life_remaining_percent = round(life_remaining_percent, 1)
        
        usage_data.append({
            'fifo_id': int_to_base36(entry.id),
            'quantity_used': abs(entry.quantity_change),  # Use absolute value for deductions
            'unit': entry.unit,
            'age_days': age_days,
            'life_remaining_percent': life_remaining_percent,
            'unit_cost': entry.unit_cost
        })
    
    return usage_data
