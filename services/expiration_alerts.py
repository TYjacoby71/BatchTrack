
from models import ProductInventory
from datetime import datetime

def get_expired_inventory():
    today = datetime.utcnow().date()
    return ProductInventory.query.filter(
        ProductInventory.expiration_date != None,
        ProductInventory.expiration_date < today,
        ProductInventory.quantity > 0
    ).all()

def archive_expired_inventory():
    today = datetime.utcnow().date()
    expired = ProductInventory.query.filter(
        ProductInventory.expiration_date < today,
        ProductInventory.quantity <= 0
    ).all()
    for row in expired:
        db.session.delete(row)
    db.session.commit()
