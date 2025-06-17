from sqlalchemy import func
from datetime import datetime
from ..models import Product, ProductInventory, ProductEvent, ProductInventoryHistory, Batch, InventoryItem
from ..extensions import db