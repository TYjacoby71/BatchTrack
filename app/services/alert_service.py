
from .base_service import CacheableService
from typing import List, Dict, Any
from app.models import Batch, Inventory, Product
from flask_login import current_user
from datetime import datetime, timedelta

class AlertService(CacheableService):
    """Consolidated service for all alert types"""
    
    def get_dashboard_alerts(self, organization_id: int) -> Dict[str, List[Dict]]:
        """Get all dashboard alerts for organization"""
        cache_key = f"dashboard_alerts_{organization_id}"
        
        return self.get_cached(cache_key, lambda: {
            'expiration': self._get_expiration_alerts(organization_id),
            'inventory': self._get_inventory_alerts(organization_id),
            'batch': self._get_batch_alerts(organization_id),
            'product': self._get_product_alerts(organization_id)
        }, ttl=300)
    
    def _get_expiration_alerts(self, organization_id: int) -> List[Dict]:
        """Get expiration alerts"""
        thirty_days = datetime.utcnow() + timedelta(days=30)
        
        expiring_inventory = Inventory.query.filter(
            Inventory.organization_id == organization_id,
            Inventory.expiration_date <= thirty_days,
            Inventory.quantity > 0
        ).all()
        
        return [
            {
                'type': 'expiration',
                'severity': 'warning' if item.expiration_date > datetime.utcnow() + timedelta(days=7) else 'danger',
                'message': f"{item.ingredient.name} expires on {item.expiration_date.strftime('%Y-%m-%d')}",
                'item_id': item.id,
                'days_until': (item.expiration_date - datetime.utcnow()).days
            }
            for item in expiring_inventory
        ]
    
    def _get_inventory_alerts(self, organization_id: int) -> List[Dict]:
        """Get low inventory alerts"""
        low_stock = Inventory.query.filter(
            Inventory.organization_id == organization_id,
            Inventory.quantity <= Inventory.minimum_stock_level,
            Inventory.quantity > 0
        ).all()
        
        return [
            {
                'type': 'low_stock',
                'severity': 'warning',
                'message': f"Low stock: {item.ingredient.name} ({item.quantity} {item.unit.symbol} remaining)",
                'item_id': item.id,
                'current_quantity': item.quantity,
                'minimum_level': item.minimum_stock_level
            }
            for item in low_stock
        ]
    
    def _get_batch_alerts(self, organization_id: int) -> List[Dict]:
        """Get batch-related alerts"""
        long_running_batches = Batch.query.filter(
            Batch.organization_id == organization_id,
            Batch.status == 'in_progress',
            Batch.started_at <= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        return [
            {
                'type': 'long_running_batch',
                'severity': 'info',
                'message': f"Batch #{batch.batch_number} has been running for over 24 hours",
                'batch_id': batch.id,
                'hours_running': (datetime.utcnow() - batch.started_at).total_seconds() / 3600
            }
            for batch in long_running_batches
        ]
    
    def _get_product_alerts(self, organization_id: int) -> List[Dict]:
        """Get product-related alerts"""
        products_low_inventory = Product.query.filter(
            Product.organization_id == organization_id,
            Product.current_inventory <= Product.minimum_stock_level
        ).all()
        
        return [
            {
                'type': 'product_low_stock',
                'severity': 'warning',
                'message': f"Product low stock: {product.name}",
                'product_id': product.id,
                'current_stock': product.current_inventory,
                'minimum_level': product.minimum_stock_level
            }
            for product in products_low_inventory
        ]
    
    def clear_organization_cache(self, organization_id: int):
        """Clear all cached alerts for an organization"""
        self.clear_cache(f"dashboard_alerts_{organization_id}")
