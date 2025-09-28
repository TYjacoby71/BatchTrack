from datetime import datetime, date
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils
from sqlalchemy import event

class InventoryItem(ScopedModelMixin, db.Model):
    """Ingredients and raw materials"""
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    # Ingredient-specific category (for density defaults, etc.)
    category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'))
    # Inventory category (separate taxonomy aligned to item type)
    inventory_category_id = db.Column(db.Integer, db.ForeignKey('inventory_category.id'), nullable=True)
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float, default=0.0)
    low_stock_threshold = db.Column(db.Float, default=0.0)
    # Density for unit conversion (g/ml for volume-weight conversions) - should never be 0
    density = db.Column(db.Float, nullable=True)
    type = db.Column(db.String(32), nullable=False, default='ingredient')  # 'ingredient', 'container', 'product', or 'product-reserved'
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='_org_name_uc'),
        db.Index('ix_inventory_item_type', 'type'),
        db.Index('ix_inventory_item_is_archived', 'is_archived'),
    )
    # Perishable tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    # Container-specific fields (for items that can hold other items)
    capacity = db.Column(db.Float, nullable=True)  # How much this container can hold
    capacity_unit = db.Column(db.String(32), nullable=True)  # Unit for storage capacity
    container_material = db.Column(db.String(64), nullable=True)
    container_type = db.Column(db.String(64), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Reference guide integration
    reference_item_name = db.Column(db.String(128), nullable=True)  # Exact match from density_reference.json
    density_source = db.Column(db.String(32), default='manual')  # 'manual', 'reference_item', 'category_default', 'auto_assigned'

    # Intermediate ingredient flag
    intermediate = db.Column(db.Boolean, default=False)

    # Global library linkage (nullable)
    global_item_id = db.Column(db.Integer, db.ForeignKey('global_item.id', ondelete='SET NULL'), nullable=True, index=True)
    # Ownership semantics: 'global' when linked, 'org' when unlinked/customized
    ownership = db.Column(db.String(16), nullable=True, index=True)

    # Organization relationship
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True, index=True)
    organization = db.relationship('Organization', backref='inventory_items')

    category = db.relationship('IngredientCategory', backref='inventory_items')
    inventory_category = db.relationship('InventoryCategory', backref='inventory_items')
    global_item = db.relationship('GlobalItem')

    # Legacy aliases removed: use capacity and capacity_unit exclusively
    @property
    def container_display_name(self):
        """Derived clean display name for containers from structured attributes.

        Example: "Glass Jar" or "Tin" if only type is present.
        Falls back to name if attributes are missing or item is not a container.
        """
        try:
            if self.type != 'container':
                return self.name
            material = (self.container_material or '').strip()
            ctype = (self.container_type or '').strip()
            if material and ctype:
                return f"{material} {ctype}".strip()
            return (ctype or material or self.name).strip()
        except Exception:
            return self.name

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
        from app.models.inventory_lot import InventoryLot

        today = datetime.now().date()
        expired_total = db.session.query(db.func.sum(InventoryLot.remaining_quantity))\
            .filter(and_(
                InventoryLot.inventory_item_id == self.id,
                InventoryLot.remaining_quantity > 0,
                InventoryLot.expiration_date != None,
                InventoryLot.expiration_date < today
            )).scalar() or 0

        return max(0, self.quantity - expired_total)

    @property
    def expired_quantity(self):
        """Get expired quantity awaiting physical removal"""
        if not self.is_perishable:
            return 0

        from datetime import datetime
        from sqlalchemy import and_
        from app.models.inventory_lot import InventoryLot

        today = datetime.now().date()
        return db.session.query(db.func.sum(InventoryLot.remaining_quantity))\
            .filter(and_(
                InventoryLot.inventory_item_id == self.id,
                InventoryLot.remaining_quantity > 0,
                InventoryLot.expiration_date != None,
                InventoryLot.expiration_date < today
            )).scalar() or 0


@event.listens_for(InventoryItem, "before_insert")
def _derive_ownership_before_insert(mapper, connection, target):
    """Derive ownership from global linkage on insert."""
    try:
        target.ownership = 'global' if getattr(target, 'global_item_id', None) else 'org'
    except Exception:
        # Best-effort; do not block insert on ownership derivation
        pass


@event.listens_for(InventoryItem, "before_update")
def _derive_ownership_before_update(mapper, connection, target):
    """Derive ownership from global linkage on update."""
    try:
        target.ownership = 'global' if getattr(target, 'global_item_id', None) else 'org'
    except Exception:
        # Best-effort; do not block update on ownership derivation
        pass

class InventoryHistory(ScopedModelMixin, db.Model):
    __tablename__ = 'inventory_history'
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    change_type = db.Column(db.String(50), nullable=True)  # manual_addition, batch_usage, spoil, trash, tester, damaged, recount
    quantity_change = db.Column(db.Float, nullable=True)
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
    # Organization relationship
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)

    # Relationships
    inventory_item = db.relationship('InventoryItem', backref='history')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    used_for_batch = db.relationship('Batch', foreign_keys=[used_for_batch_id])
    user = db.relationship('User')

    def __repr__(self):
        return f'<InventoryHistory {self.id}: {self.change_type} {self.quantity_change} {self.unit}>'


@event.listens_for(InventoryHistory, "before_insert")
def _set_org_on_history(mapper, connection, target):
    if getattr(target, "organization_id", None) is None and target.inventory_item_id:
        inv_tbl = InventoryItem.__table__
        row = connection.execute(
            inv_tbl.select()
                   .with_only_columns(inv_tbl.c.organization_id)
                   .where(inv_tbl.c.id == target.inventory_item_id)
        ).first()
        if row:
            target.organization_id = row[0]

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