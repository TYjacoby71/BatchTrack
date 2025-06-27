
from flask import Blueprint, jsonify, request
from flask_login import login_required
from ...models import db, InventoryItem, InventoryHistory, Batch, BatchIngredient, ExtraBatchIngredient, BatchContainer, ExtraBatchContainer
from datetime import datetime, date
from ...utils.fifo_generator import int_to_base36

fifo_api_bp = Blueprint('fifo_api', __name__)

@fifo_api_bp.route('/api/batch-inventory-summary/<int:batch_id>')
@login_required
def get_batch_inventory_summary(batch_id):
    """Get inventory summary for all ingredients used in a batch"""
    try:
        # Get batch with organization scoping
        from ...models import Batch
        batch = Batch.scoped().filter_by(id=batch_id).first_or_404()
        
        # Get all batch ingredients and extra ingredients
        ingredients_used = []
        
        # Regular batch ingredients
        for batch_ingredient in batch.batch_ingredients:
            fifo_usage = get_batch_fifo_usage(batch_ingredient.inventory_item_id, batch_id)
            ingredients_used.append({
                'inventory_item_id': batch_ingredient.inventory_item_id,
                'name': batch_ingredient.inventory_item.name,
                'quantity_used': batch_ingredient.quantity_used,
                'unit': batch_ingredient.unit,
                'cost_per_unit': batch_ingredient.cost_per_unit,
                'fifo_sources': fifo_usage
            })
        
        # Extra batch ingredients
        for extra_ingredient in batch.extra_ingredients:
            fifo_usage = get_batch_fifo_usage(extra_ingredient.inventory_item_id, batch_id)
            ingredients_used.append({
                'inventory_item_id': extra_ingredient.inventory_item_id,
                'name': extra_ingredient.inventory_item.name,
                'quantity_used': extra_ingredient.quantity,
                'unit': extra_ingredient.unit,
                'cost_per_unit': extra_ingredient.cost_per_unit,
                'fifo_sources': fifo_usage
            })
        
        return jsonify({
            'success': True,
            'batch_label': batch.label_code,
            'ingredients_used': ingredients_used
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
                'id': item.id,
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
            usage_data = get_batch_fifo_usage(batch_ing.inventory_item_id, batch_id)
            total_used = sum(usage['quantity_used'] for usage in usage_data)
            
            ingredient_summary.append({
                'name': batch_ing.inventory_item.name,
                'total_used': total_used,
                'unit': batch_ing.unit,
                'fifo_usage': usage_data
            })
        
        # Extra ingredients
        extra_ingredients = ExtraBatchIngredient.query.filter_by(batch_id=batch_id).all()
        for extra_ing in extra_ingredients:
            usage_data = get_batch_fifo_usage(extra_ing.inventory_item_id, batch_id)
            total_used = sum(usage['quantity_used'] for usage in usage_data)
            
            ingredient_summary.append({
                'name': extra_ing.inventory_item.name,
                'total_used': total_used,
                'unit': extra_ing.unit,
                'fifo_usage': usage_data
            })
        
        # Add containers
        batch_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch_id).all()
        
        container_summary = []
        for container in batch_containers:
            container_summary.append({
                'name': container.container.name,
                'quantity_used': container.quantity_used,
                'cost_each': container.cost_each,
                'type': 'regular'
            })
        
        for extra_container in extra_containers:
            container_summary.append({
                'name': extra_container.container.name,
                'quantity_used': extra_container.quantity_used,
                'cost_each': extra_container.cost_each,
                'type': 'extra'
            })
        
        return jsonify({
            'batch': {
                'label_code': batch.label_code,
                'recipe_name': batch.recipe.name,
                'scale': batch.scale
            },
            'ingredient_summary': ingredient_summary,
            'container_summary': container_summary
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_batch_fifo_usage(inventory_id, batch_id):
    """Get FIFO usage data for a specific ingredient in a specific batch"""
    # Get deduction history entries for this batch
    deduction_entries = InventoryHistory.query.filter_by(
        inventory_item_id=inventory_id,
        used_for_batch_id=batch_id
    ).filter(
        InventoryHistory.quantity_change < 0  # Only deductions
    ).all()
    
    usage_data = []
    for entry in deduction_entries:
        age_days = None
        life_remaining_percent = None
        
        # Get the source FIFO entry to calculate age from its creation date
        source_entry = None
        if entry.fifo_reference_id:
            source_entry = InventoryHistory.query.get(entry.fifo_reference_id)
        
        if source_entry and source_entry.timestamp:
            # Get the batch to use its start timestamp for age calculation
            batch = Batch.query.get(batch_id)
            batch_start = batch.started_at if batch else datetime.utcnow()
            
            # Calculate age from the source entry's creation date to when batch started
            age_timedelta = batch_start - source_entry.timestamp
            age_days = age_timedelta.days
            age_hours = age_timedelta.total_seconds() / 3600
            
            if source_entry.is_perishable and source_entry.expiration_date:
                # Use expiration date for more precise calculation
                total_life_seconds = (source_entry.expiration_date - source_entry.timestamp).total_seconds()
                used_life_seconds = (batch_start - source_entry.timestamp).total_seconds()
                
                if total_life_seconds > 0:
                    life_remaining_percent = max(0, 100 - ((used_life_seconds / total_life_seconds) * 100))
                    life_remaining_percent = round(life_remaining_percent, 1)
                else:
                    life_remaining_percent = 0.0
            elif source_entry.is_perishable and source_entry.shelf_life_days:
                # Fallback to shelf life days calculation with hours precision
                shelf_life_hours = source_entry.shelf_life_days * 24
                life_remaining_percent = max(0, 100 - ((age_hours / shelf_life_hours) * 100))
                life_remaining_percent = round(life_remaining_percent, 1)
        elif entry.timestamp:
            # Fallback to using the deduction entry's timestamp if no source found
            batch = Batch.query.get(batch_id)
            batch_start = batch.started_at if batch else datetime.utcnow()
            age_days = (batch_start - entry.timestamp).days
            
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
