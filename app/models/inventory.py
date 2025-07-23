
from datetime import datetime, date
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class InventoryItem(ScopedModelMixin, db.Model):
    """Ingredients and raw materials"""
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'))
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float, default=0.0)
    low_stock_threshold = db.Column(db.Float, default=0.0)
    density = db.Column(db.Float, nullable=True)  # g/ml for volume-weight conversions
    type = db.Column(db.String(32), nullable=False, default='ingredient')  # 'ingredient', 'container', 'product', or 'product-reserved'
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    # Perishable tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    # Container-specific fields
    storage_amount = db.Column(db.Float, nullable=True)
    storage_unit = db.Column(db.String(32), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    # Density for unit conversion (g/mL)
    density = db.Column(db.Float, nullable=True)

    # Intermediate ingredient flag
    intermediate = db.Column(db.Boolean, default=False)

    # Organization relationship
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship('Organization', backref='inventory_items')

    category = db.relationship('IngredientCategory', backref='inventory_items')

    def belongs_to_user(self):
        """Check if this record belongs to the current user's organization"""
        if not current_user.is_authenticated:
            return False
        return self.organization_id == current_user.organization_id

    @property
    def available_quantity(self):
        """Get non-expired quantity available for use"""
        if not self.is_perishable:
            return self.quantity

        from datetime import datetime
        from sqlalchemy import and_

        today = datetime.now().date()
        expired_total = db.session.query(db.func.sum(InventoryHistory.remaining_quantity))\
            .filter(and_(
                InventoryHistory.inventory_item_id == self.id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today
            )).scalar() or 0

        return max(0, self.quantity - expired_total)

    @property 
    def expired_quantity(self):
        """Get expired quantity awaiting physical removal"""
        if not self.is_perishable:
            return 0

        from datetime import datetime
        from sqlalchemy import and_

        today = datetime.now().date()
        return db.session.query(db.func.sum(InventoryHistory.remaining_quantity))\
            .filter(and_(
                InventoryHistory.inventory_item_id == self.id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today
            )).scalar() or 0

class InventoryHistory(ScopedModelMixin, db.Model):
    __tablename__ = 'inventory_history'
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    change_type = db.Column(db.String(32), nullable=False)  # manual_addition, batch_usage, spoil, trash, tester, damaged, recount
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    remaining_quantity = db.Column(db.Float, nullable=True)  # For FIFO tracking
    unit_cost = db.Column(db.Float, nullable=True)
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('inventory_history.id'), nullable=True)
    fifo_code = db.Column(db.String(32), nullable=True)  # Base32 encoded unique identifier
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    quantity_used = db.Column(db.Float, default=0.0)  # Track actual consumption vs deduction
    used_for_batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)  # Track which batch used this
    # Expiration tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    # Relationships
    inventory_item = db.relationship('InventoryItem', backref='history')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    used_for_batch = db.relationship('Batch', foreign_keys=[used_for_batch_id])
    user = db.relationship('User')

class BatchInventoryLog(ScopedModelMixin, db.Model):
    """Log batch impacts on inventory for debugging"""
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)  # deduct, credit
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    old_stock = db.Column(db.Float, nullable=False)
    new_stock = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    batch = db.relationship('Batch')
    inventory_item = db.relationship('InventoryItem')
