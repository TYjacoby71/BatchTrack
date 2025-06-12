
from models import Recipe, Batch, InventoryItem, ProductInventory
from datetime import datetime, timedelta

class DashboardService:
    @staticmethod
    def get_dashboard_data():
        """Get all dashboard data"""
        data = {
            'recipes': Recipe.query.filter_by(is_locked=False).count(),
            'active_batches': Batch.query.filter_by(status='active').count(),
            'total_inventory': InventoryItem.query.count(),
            'low_stock_items': DashboardService._get_low_stock_count()
        }
        return data
    
    @staticmethod
    def _get_low_stock_count():
        """Count items with low stock"""
        return InventoryItem.query.filter(
            InventoryItem.quantity <= InventoryItem.low_stock_threshold
        ).count()
    
    @staticmethod
    def get_recent_batches(limit=5):
        """Get recent batch activity"""
        return Batch.query.order_by(Batch.created_at.desc()).limit(limit).all()
