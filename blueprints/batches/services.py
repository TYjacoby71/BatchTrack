
from models import Batch, Recipe, InventoryItem, BatchIngredient, db
from datetime import datetime

class BatchService:
    @staticmethod
    def can_start_batch(recipe_id, scale=1.0):
        """Check if batch can be started with available inventory"""
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return False, "Recipe not found"
        
        # Check ingredient availability
        for ingredient in recipe.ingredients:
            required_qty = ingredient.quantity * scale
            available = InventoryItem.query.filter_by(
                name=ingredient.ingredient_name
            ).first()
            
            if not available or available.quantity < required_qty:
                return False, f"Insufficient {ingredient.ingredient_name}"
        
        return True, "Ready to start"
    
    @staticmethod
    def start_batch(recipe_id, scale=1.0, containers=None):
        """Start a new batch"""
        recipe = Recipe.query.get(recipe_id)
        
        # Create batch
        batch = Batch(
            recipe_id=recipe_id,
            scale=scale,
            status='active',
            created_at=datetime.utcnow()
        )
        db.session.add(batch)
        db.session.flush()
        
        # Deduct ingredients
        for ingredient in recipe.ingredients:
            required_qty = ingredient.quantity * scale
            inventory_item = InventoryItem.query.filter_by(
                name=ingredient.ingredient_name
            ).first()
            
            if inventory_item:
                inventory_item.quantity -= required_qty
        
        db.session.commit()
        return batch
