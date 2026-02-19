"""Inventory lot model.

Synopsis:
Defines FIFO inventory lots with base quantities and expiration data.

Glossary:
- Inventory lot: Physical stock unit tracked for FIFO.
- Base quantity: Integer quantity stored in canonical units.
"""

from datetime import datetime, timezone

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
from .mixins import ScopedModelMixin


class InventoryLot(ScopedModelMixin, db.Model):
    """
    Represents actual physical inventory lots for FIFO tracking.
    Each lot represents a specific batch of inventory with its own cost and expiration.
    """

    __tablename__ = "inventory_lot"

    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_item.id"), nullable=False
    )

    # Lot tracking
    remaining_quantity = db.Column(db.Float, nullable=False, default=0.0)
    original_quantity = db.Column(db.Float, nullable=False)
    remaining_quantity_base = db.Column(db.BigInteger, nullable=False, default=0)
    original_quantity_base = db.Column(db.BigInteger, nullable=False, default=0)
    unit = db.Column(db.String(32), nullable=False)
    unit_cost = db.Column(db.Float, nullable=False, default=0.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    received_date = db.Column(
        db.DateTime, default=TimezoneUtils.utc_now, nullable=False
    )

    # Expiration tracking
    expiration_date = db.Column(db.DateTime, nullable=True)
    shelf_life_days = db.Column(db.Integer, nullable=True)

    # Source tracking
    source_type = db.Column(
        db.String(50), nullable=False
    )  # 'restock', 'finished_batch', etc.
    source_notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # FIFO identification
    fifo_code = db.Column(db.String(32), nullable=True, unique=True)

    # Batch relationship (for lots created from finished batches)
    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"), nullable=True)

    # Organization relationship
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=True
    )

    # Relationships
    inventory_item = db.relationship(
        "InventoryItem", foreign_keys=[inventory_item_id], backref="lots"
    )
    organization = db.relationship("Organization", foreign_keys=[organization_id])

    @property
    def is_perishable(self):
        """Check if this lot is perishable based on expiration date or parent item"""
        return (self.expiration_date is not None) or (
            self.inventory_item and self.inventory_item.is_perishable
        )

    @property
    def is_expired(self):
        """Check if this lot is expired"""
        if not self.expiration_date:
            return False
        # Compare dates only (both are date objects, no timezone issues)
        today = datetime.now(timezone.utc).date()
        return self.expiration_date < today

    @property
    def days_until_expiration(self):
        """Get days until expiration (negative if already expired)"""
        if not self.expiration_date:
            return None
        # Compare dates only (both are date objects, no timezone issues)
        today = datetime.now(timezone.utc).date()
        delta = self.expiration_date - today
        return delta.days

    # Remove duplicate relationship declarations (kept canonical ones above)
    user = db.relationship("User")
    batch = db.relationship("Batch", backref="created_lots")

    # Constraints and indexes
    __table_args__ = (
        db.CheckConstraint(
            "remaining_quantity >= 0", name="check_remaining_quantity_non_negative"
        ),
        db.CheckConstraint(
            "original_quantity > 0", name="check_original_quantity_positive"
        ),
        db.CheckConstraint(
            "remaining_quantity <= original_quantity",
            name="check_remaining_not_exceeds_original",
        ),
        db.CheckConstraint(
            "remaining_quantity_base >= 0",
            name="check_remaining_quantity_base_non_negative",
        ),
        db.CheckConstraint(
            "original_quantity_base > 0", name="check_original_quantity_base_positive"
        ),
        db.CheckConstraint(
            "remaining_quantity_base <= original_quantity_base",
            name="check_remaining_base_not_exceeds_original",
        ),
        db.Index("ix_inventory_lot_org", "organization_id"),
    )

    def __repr__(self):
        return f"<InventoryLot {self.id}: {self.remaining_quantity}/{self.original_quantity} {self.unit}>"

    @property
    def display_code(self):
        """Get the customer-facing lot identifier"""
        return self.fifo_code or f"LOT-{self.id}"

    @property
    def lot_number(self):
        """Legacy compatibility - return display code as lot number"""
        return self.display_code

    @property
    def is_depleted(self):
        """Check if this lot is completely consumed"""
        return int(self.remaining_quantity_base or 0) <= 0

    # is_expired defined above (lines 57-63) using date compare;
    # retain a single implementation to avoid confusion.

    @property
    def consumption_percentage(self):
        """Get percentage of lot that has been consumed"""
        if self.original_quantity <= 0:
            return 100.0
        return (
            (self.original_quantity - self.remaining_quantity) / self.original_quantity
        ) * 100

    def consume(self, quantity: float) -> bool:
        """
        Consume quantity from this lot.
        Returns True if successful, False if insufficient quantity.
        """
        if quantity < 0:
            return False

        from app.services.quantity_base import (
            sync_lot_quantities_from_base,
            to_base_quantity,
        )

        quantity_base = to_base_quantity(
            amount=quantity,
            unit_name=self.unit,
            ingredient_id=self.inventory_item_id,
            density=getattr(self.inventory_item, "density", None),
        )
        if int(self.remaining_quantity_base or 0) < int(quantity_base):
            return False

        self.remaining_quantity_base = int(self.remaining_quantity_base or 0) - int(
            quantity_base
        )
        sync_lot_quantities_from_base(self, self.inventory_item)
        return True

    def credit_back(self, quantity: float) -> bool:
        """
        Credit quantity back to this lot (for returns, corrections).
        Returns True if successful, False if would exceed original quantity.
        """
        if quantity < 0:
            return False

        from app.services.quantity_base import (
            sync_lot_quantities_from_base,
            to_base_quantity,
        )

        quantity_base = to_base_quantity(
            amount=quantity,
            unit_name=self.unit,
            ingredient_id=self.inventory_item_id,
            density=getattr(self.inventory_item, "density", None),
        )
        new_remaining_base = int(self.remaining_quantity_base or 0) + int(quantity_base)
        if new_remaining_base > int(self.original_quantity_base or 0):
            return False

        self.remaining_quantity_base = new_remaining_base
        sync_lot_quantities_from_base(self, self.inventory_item)
        return True
