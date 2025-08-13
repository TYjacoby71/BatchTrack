
from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class UnifiedInventoryHistory(ScopedModelMixin, db.Model):
    """Unified history table for all inventory changes (ingredients, products, containers)"""
    __tablename__ = 'unified_inventory_history'

    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    change_type = db.Column(db.String(50), nullable=False, index=True)
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    unit_cost = db.Column(db.Float, nullable=True)
    remaining_quantity = db.Column(db.Float, default=0.0)

    # FIFO Tracking
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('unified_inventory_history.id'), nullable=True)
    fifo_code = db.Column(db.String(64), nullable=True, index=True)

    # Contextual Information
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    quantity_used = db.Column(db.Float, default=0.0)
    used_for_batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)

    # Perishability
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True, index=True)

    # Location and Quality
    location_id = db.Column(db.String(128), nullable=True)
    location_name = db.Column(db.String(128), nullable=True)
    temperature_at_time = db.Column(db.Float, nullable=True)
    quality_status = db.Column(db.String(32), nullable=True)
    compliance_status = db.Column(db.String(32), nullable=True)
    quality_checked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # --- Product-Specific Fields (Nullable for ingredient entries) ---
    customer = db.Column(db.String(255), nullable=True)
    sale_price = db.Column(db.Float, nullable=True)
    order_id = db.Column(db.String(255), nullable=True)
    reservation_id = db.Column(db.String(64), nullable=True)
    is_reserved = db.Column(db.Boolean, default=False)
    sale_location = db.Column(db.String(64), nullable=True)
    marketplace_order_id = db.Column(db.String(128), nullable=True)
    marketplace_source = db.Column(db.String(32), nullable=True)

    # Additional tracking
    batch_number = db.Column(db.String(128), nullable=True)
    lot_number = db.Column(db.String(128), nullable=True)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    fifo_source = db.Column(db.String(128), nullable=True)

    # Relationships
    inventory_item = db.relationship('InventoryItem', foreign_keys=[inventory_item_id], backref='unified_history')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    used_for_batch = db.relationship('Batch', foreign_keys=[used_for_batch_id])
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    quality_checker = db.relationship('User', foreign_keys=[quality_checked_by])
    fifo_reference = db.relationship('UnifiedInventoryHistory', remote_side=[id])

    # Indexes for performance
    __table_args__ = (
        db.Index('idx_unified_item_remaining', 'inventory_item_id', 'remaining_quantity'),
        db.Index('idx_unified_item_timestamp', 'inventory_item_id', 'timestamp'),
        db.Index('idx_unified_fifo_code', 'fifo_code'),
        db.Index('idx_unified_change_type', 'change_type'),
        db.Index('idx_unified_expiration', 'expiration_date'),
    )

    def __repr__(self):
        return f'<UnifiedInventoryHistory {self.id} | Item {self.inventory_item_id} | {self.change_type}: {self.quantity_change}>'
