from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class UnifiedInventoryHistory(ScopedModelMixin, db.Model):
    """
    Event log for ALL inventory movements and adjustments.

    This table records EVENTS, not lots. For FIFO lot tracking, see InventoryLot.
    Every inventory change creates exactly one event record here.
    """
    __tablename__ = 'unified_inventory_history'

    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False, index=True)
    # Use timezone-safe application helper for consistency
    from ..utils.timezone_utils import TimezoneUtils as _TZ
    timestamp = db.Column(db.DateTime, default=_TZ.utc_now, nullable=False, index=True)
    change_type = db.Column(db.String(50), nullable=False, index=True)
    quantity_change = db.Column(db.Float, nullable=False)
    quantity_change_base = db.Column(db.BigInteger, nullable=False, default=0)
    unit = db.Column(db.String(50), nullable=False)
    # Lot reference for tracking which lots were affected
    affected_lot_id = db.Column(db.Integer, db.ForeignKey('inventory_lot.id'), nullable=True)

    # Legacy FIFO fields (deprecated - use InventoryLot instead)
    remaining_quantity = db.Column(db.Float, nullable=True, default=0.0)  # DEPRECATED
    remaining_quantity_base = db.Column(db.BigInteger, nullable=True)
    unit_cost = db.Column(db.Float, nullable=True, default=0.0)
    valuation_method = db.Column(db.String(16), nullable=True)  # 'fifo' | 'average'
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('unified_inventory_history.id'), nullable=True)
    fifo_code = db.Column(db.String(32), nullable=True)

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
    
    # Organization scoping
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Relationships
    inventory_item = db.relationship('InventoryItem', foreign_keys=[inventory_item_id], backref='unified_history')
    affected_lot = db.relationship('InventoryLot', foreign_keys=[affected_lot_id], backref='events')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    used_for_batch = db.relationship('Batch', foreign_keys=[used_for_batch_id])
    user = db.relationship('User', foreign_keys=[created_by])
    organization = db.relationship('Organization', foreign_keys=[organization_id])
    quality_checker = db.relationship('User', foreign_keys=[quality_checked_by])
    fifo_reference = db.relationship('UnifiedInventoryHistory', remote_side=[id])

    # Indexes for performance
    __table_args__ = (
        db.Index('idx_unified_item_remaining', 'inventory_item_id', 'remaining_quantity'),
        db.Index('idx_unified_item_timestamp', 'inventory_item_id', 'timestamp'),
        db.Index('idx_unified_fifo_code', 'fifo_code'),
        db.Index('idx_unified_change_type', 'change_type'),
        db.Index('idx_unified_expiration', 'expiration_date'),
        db.Index('ix_unified_history_org', 'organization_id'),
    )

    def __repr__(self):
        return f'<UnifiedInventoryHistory {self.id} | Item {self.inventory_item_id} | {self.change_type}: {self.quantity_change}>'

    # --- Naming clarity aliases ---
    @property
    def event_code(self):
        """Alias for fifo_code: customer-facing event identifier string."""
        return self.fifo_code

    @event_code.setter
    def event_code(self, value):
        self.fifo_code = value

    @property
    def reference_event_id(self):
        """Alias for fifo_reference_id: references another inventory event id."""
        return self.fifo_reference_id

    @reference_event_id.setter
    def reference_event_id(self, value):
        self.fifo_reference_id = value

    @property
    def reference_lot_id(self):
        """Preferred alias for affected_lot_id: references the lot involved in this event."""
        return self.affected_lot_id

    @reference_lot_id.setter
    def reference_lot_id(self, value):
        self.affected_lot_id = value