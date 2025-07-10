from ..models import db, ProductSKU, InventoryItem
from sqlalchemy import and_
from typing import List, Dict
from flask_login import current_user

# Backward compatibility - redirect to unified service
from .combined_inventory_alerts import CombinedInventoryAlertService

class ProductAlertService:
    """Backward compatibility class - redirects to unified service"""

    @staticmethod
    def get_low_stock_skus():
        return CombinedInventoryAlertService.get_low_stock_skus()

    @staticmethod
    def get_out_of_stock_skus():
        return CombinedInventoryAlertService.get_out_of_stock_skus()

    @staticmethod
    def get_product_stock_summary():
        return CombinedInventoryAlertService.get_product_stock_summary()