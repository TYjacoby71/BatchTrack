
from models import Recipe, InventoryItem, Unit

class ValidationService:
    @staticmethod
    def validate_recipe_data(data):
        """Validate recipe form data"""
        errors = []
        
        if not data.get('name'):
            errors.append('Recipe name is required')
        
        if not data.get('instructions'):
            errors.append('Instructions are required')
        
        return errors
    
    @staticmethod
    def validate_inventory_data(data):
        """Validate inventory form data"""
        errors = []
        
        if not data.get('name'):
            errors.append('Item name is required')
        
        try:
            quantity = float(data.get('quantity', 0))
            if quantity < 0:
                errors.append('Quantity cannot be negative')
        except ValueError:
            errors.append('Invalid quantity format')
        
        return errors
