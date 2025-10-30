
from datetime import datetime, timedelta, timezone
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class Reservation(ScopedModelMixin, db.Model):
    """Individual reservation line items - replaces FIFO remaining_quantity tracking"""
    __tablename__ = 'reservation'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # CORE IDENTIFICATION
    order_id = db.Column(db.String(128), nullable=False, index=True)
    reservation_id = db.Column(db.String(128), nullable=True)  # Optional internal reservation ID
    
    # PRODUCT REFERENCE
    product_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)  # Original product
    reserved_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)  # Reserved inventory item
    
    # QUANTITY AND PRICING
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    unit_cost = db.Column(db.Float, nullable=True)
    sale_price = db.Column(db.Float, nullable=True)
    customer = db.Column(db.String(128), nullable=True)
    
    # SOURCE TRACKING (which FIFO batch this came from)
    source_fifo_id = db.Column(db.Integer, nullable=True)  # Reference to the original FIFO entry
    source_batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    
    # STATUS AND LIFECYCLE
    status = db.Column(db.String(32), default='active')  # active, released, expired, converted_to_sale
    source = db.Column(db.String(64), default='shopify')  # shopify, manual, etc.
    
    # TIMESTAMPS
    # STORAGE: All times stored as timezone-aware UTC
    # DISPLAY: Templates/APIs convert to user's timezone
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=True)  # Optional expiration
    released_at = db.Column(db.DateTime, nullable=True)
    converted_at = db.Column(db.DateTime, nullable=True)
    
    # METADATA
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # RELATIONSHIPS
    product_item = db.relationship('InventoryItem', foreign_keys=[product_item_id])
    reserved_item = db.relationship('InventoryItem', foreign_keys=[reserved_item_id])
    source_batch = db.relationship('Batch', foreign_keys=[source_batch_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    
    # INDEXES
    __table_args__ = (
        db.Index('idx_order_status', 'order_id', 'status'),
        db.Index('idx_reserved_item_status', 'reserved_item_id', 'status'),
        db.Index('idx_expires_at', 'expires_at'),
    )
    
    @property
    def is_active(self):
        """Check if reservation is still active"""
        return self.status == 'active'
    
    @property
    def is_expired(self):
        """
        Check if reservation has expired.
        
        STORAGE: expires_at stored in UTC (timezone-aware)
        COMPARISON: Safe comparison with current UTC time
        """
        if not self.expires_at:
            return False
        # Ensure both datetimes are timezone-aware for safe comparison
        expires_at = TimezoneUtils.ensure_timezone_aware(self.expires_at)
        return datetime.now(timezone.utc) > expires_at
    
    def mark_released(self):
        """
        Mark reservation as released.
        
        STORAGE: Sets released_at in UTC (timezone-aware)
        DISPLAY: UI will convert to user's timezone
        """
        self.status = 'released'
        self.released_at = datetime.now(timezone.utc)
    
    def mark_converted_to_sale(self):
        """
        Mark reservation as converted to sale.
        
        STORAGE: Sets converted_at in UTC (timezone-aware)
        DISPLAY: UI will convert to user's timezone
        """
        self.status = 'converted_to_sale'
        self.converted_at = datetime.now(timezone.utc)
    
    def mark_expired(self):
        """
        Mark reservation as expired.
        
        STORAGE: Sets released_at in UTC (timezone-aware)
        DISPLAY: UI will convert to user's timezone
        """
        self.status = 'expired'
        self.released_at = datetime.now(timezone.utc)
    
    def __repr__(self):
        return f'<Reservation {self.order_id}: {self.quantity} {self.unit}>'
