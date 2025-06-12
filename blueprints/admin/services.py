
from models import db, ProductInventory, User
from datetime import datetime

class AdminService:
    @staticmethod
    def archive_zeroed_inventory():
        """Archive all inventory items with zero quantity"""
        zero_items = ProductInventory.query.filter(ProductInventory.quantity <= 0).all()
        count = len(zero_items)
        
        for item in zero_items:
            db.session.delete(item)
        
        db.session.commit()
        return count
    
    @staticmethod
    def get_system_stats():
        """Get system statistics"""
        stats = {
            'total_users': User.query.count(),
            'total_inventory_items': ProductInventory.query.count(),
            'zero_quantity_items': ProductInventory.query.filter(ProductInventory.quantity <= 0).count()
        }
        return stats
