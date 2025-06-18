
from ..models import InventoryItem
from sqlalchemy import and_

def get_low_stock_ingredients():
    return InventoryItem.query.filter(
        and_(
            InventoryItem.low_stock_threshold > 0,
            InventoryItem.current_stock <= InventoryItem.low_stock_threshold
        )
    ).all()
