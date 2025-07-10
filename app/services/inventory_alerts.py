
# Backward compatibility - redirect to unified service
from .combined_inventory_alerts import CombinedInventoryAlertService

def get_low_stock_ingredients():
    """Backward compatibility function"""
    return CombinedInventoryAlertService.get_low_stock_ingredients()
