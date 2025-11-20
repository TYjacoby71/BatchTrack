
import os
from flask_login import current_user
from ..extensions import db
import sqlalchemy as sa
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

# Dialect-aware helpers to allow SQLite tests while keeping PG features in prod
def _is_postgres_url(url: str) -> bool:
    if not url:
        return False
    url = url.lower()
    return (
        url.startswith("postgres://")
        or url.startswith("postgresql://")
        or url.startswith("postgresql+psycopg2://")
    )

_IS_PG = _is_postgres_url(os.environ.get("DATABASE_URL", ""))



class Batch(ScopedModelMixin, db.Model):
    __tablename__ = 'batch'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    label_code = db.Column(db.String(32), unique=True)
    batch_type = db.Column(db.String(32), nullable=False)  # 'ingredient' or 'product'
    projected_yield = db.Column(db.Float)
    projected_yield_unit = db.Column(db.String(50))
    # Product assignment for finish batch
    sku_id = db.Column(db.Integer, db.ForeignKey('product_sku.id'), nullable=True)
    final_quantity = db.Column(db.Float)
    output_unit = db.Column(db.String(50))
    scale = db.Column(db.Float, default=1.0)
    status = db.Column(db.String(50), default='in_progress')  # in_progress, completed, failed, cancelled
    status_reason = db.Column(db.Text)  # Optional reason for status change
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    total_cost = db.Column(db.Float)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    started_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    inventory_credited = db.Column(db.Boolean, default=False)  # Track if inventory was returned
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer)
    expiration_date = db.Column(db.DateTime)
    remaining_quantity = db.Column(db.Float, nullable=True)
    portioning_data = db.Column(db.JSON, nullable=True)
    # Absolute additive columns (no new units)
    is_portioned = db.Column(db.Boolean, nullable=True)
    portion_name = db.Column(db.String(64), nullable=True)
    projected_portions = db.Column(db.Integer, nullable=True)
    final_portions = db.Column(db.Integer, nullable=True)
    plan_snapshot = db.Column(db.JSON, nullable=True)
    portion_unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)

    # Costing policy snapshot
    cost_method = db.Column(db.String(16), nullable=True)  # 'fifo' | 'average'
    cost_method_locked_at = db.Column(db.DateTime, nullable=True)

    recipe = db.relationship('Recipe', backref='batches')
    sku = db.relationship('ProductSKU', foreign_keys=[sku_id], backref='batches')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add computed columns dynamically for PostgreSQL only
        if _IS_PG and not hasattr(self.__class__, '_pg_columns_added'):
            self._add_pg_computed_columns()
            self.__class__._pg_columns_added = True

    @classmethod
    def _add_pg_computed_columns(cls):
        """Add PostgreSQL computed columns at runtime"""
        if not _IS_PG:
            return
            
        # Add computed columns
        cls.vessel_fill_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'vessel_fill_pct'))::numeric", persisted=True), nullable=True)
        cls.candle_fragrance_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'candle_fragrance_pct'))::numeric", persisted=True), nullable=True)
        cls.candle_vessel_ml = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'candle_vessel_ml'))::numeric", persisted=True), nullable=True)
        cls.soap_superfat = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'soap_superfat'))::numeric", persisted=True), nullable=True)
        cls.soap_water_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'soap_water_pct'))::numeric", persisted=True), nullable=True)
        cls.soap_lye_type = db.Column(sa.Text(), sa.Computed("((plan_snapshot -> 'category_extension') ->> 'soap_lye_type')", persisted=True), nullable=True)
        cls.baker_base_flour_g = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'baker_base_flour_g'))::numeric", persisted=True), nullable=True)
        cls.baker_water_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'baker_water_pct'))::numeric", persisted=True), nullable=True)
        cls.baker_salt_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'baker_salt_pct'))::numeric", persisted=True), nullable=True)
        cls.baker_yeast_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'baker_yeast_pct'))::numeric", persisted=True), nullable=True)
        cls.cosm_emulsifier_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'cosm_emulsifier_pct'))::numeric", persisted=True), nullable=True)
        cls.cosm_preservative_pct = db.Column(sa.Numeric(), sa.Computed("(((plan_snapshot -> 'category_extension') ->> 'cosm_preservative_pct'))::numeric", persisted=True), nullable=True)
        
        # Add indexes for the computed columns (PostgreSQL only)
        # Note: These indexes are also created in Alembic migrations for production
        cls.__table__.indexes.update({
            db.Index('ix_batch_vessel_fill_pct', cls.vessel_fill_pct),
            db.Index('ix_batch_candle_fragrance_pct', cls.candle_fragrance_pct),
            db.Index('ix_batch_candle_vessel_ml', cls.candle_vessel_ml),
            db.Index('ix_batch_soap_superfat', cls.soap_superfat),
            db.Index('ix_batch_soap_water_pct', cls.soap_water_pct),
            db.Index('ix_batch_soap_lye_type', cls.soap_lye_type),
            db.Index('ix_batch_baker_base_flour_g', cls.baker_base_flour_g),
            db.Index('ix_batch_baker_water_pct', cls.baker_water_pct),
            db.Index('ix_batch_baker_salt_pct', cls.baker_salt_pct),
            db.Index('ix_batch_baker_yeast_pct', cls.baker_yeast_pct),
            db.Index('ix_batch_cosm_emulsifier_pct', cls.cosm_emulsifier_pct),
            db.Index('ix_batch_cosm_preservative_pct', cls.cosm_preservative_pct),
        })

    # Define table args without computed column indexes - they'll be added dynamically
    __table_args__ = (
        db.Index('ix_batch_org', 'organization_id'),
    )

class BatchIngredient(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)

    batch = db.relationship('Batch', backref='batch_ingredients')
    inventory_item = db.relationship('InventoryItem', backref='batch_usages')

class BatchContainer(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_container'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    container_quantity = db.Column(db.Integer, nullable=False)  # Number of containers used
    quantity_used = db.Column(db.Integer, nullable=False)  # Same as container_quantity for backwards compatibility
    fill_quantity = db.Column(db.Float)  # How much product each container holds
    fill_unit = db.Column(db.String(32))  # Unit for fill_quantity
    cost_each = db.Column(db.Float)  # Cost per container

    batch = db.relationship('Batch', backref='containers')
    inventory_item = db.relationship('InventoryItem')

class BatchConsumable(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_consumable'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)

    batch = db.relationship('Batch', backref='consumables')
    inventory_item = db.relationship('InventoryItem')

    __table_args__ = (
        db.Index('ix_batch_consumable_batch_id', 'batch_id'),
        db.Index('ix_batch_consumable_inventory_item_id', 'inventory_item_id'),
        db.Index('ix_batch_consumable_organization_id', 'organization_id'),
    )

class ExtraBatchContainer(ScopedModelMixin, db.Model):
    __tablename__ = 'extra_batch_container'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    container_quantity = db.Column(db.Integer, nullable=False)  # Number of containers used
    quantity_used = db.Column(db.Integer, nullable=False)  # Same as container_quantity for backwards compatibility
    fill_quantity = db.Column(db.Float)  # How much product each container holds
    fill_unit = db.Column(db.String(32))  # Unit for fill_quantity
    cost_each = db.Column(db.Float)  # Cost per container
    reason = db.Column(db.String(20), nullable=False, default='extra_yield')  # Track why container was added

    batch = db.relationship('Batch', backref='extra_containers')
    inventory_item = db.relationship('InventoryItem')

class BatchTimer(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_timer'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default='active')  # active, completed, cancelled
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    batch = db.relationship('Batch', backref='timers')

class ExtraBatchIngredient(ScopedModelMixin, db.Model):
    __tablename__ = 'extra_batch_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)

    batch = db.relationship('Batch', backref='extra_ingredients')
    inventory_item = db.relationship('InventoryItem', backref='extra_batch_usages')

class ExtraBatchConsumable(ScopedModelMixin, db.Model):
    __tablename__ = 'extra_batch_consumable'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    reason = db.Column(db.String(20), nullable=False, default='extra_use')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)

    batch = db.relationship('Batch', backref='extra_consumables')
    inventory_item = db.relationship('InventoryItem')

    __table_args__ = (
        db.Index('ix_extra_batch_consumable_batch_id', 'batch_id'),
        db.Index('ix_extra_batch_consumable_inventory_item_id', 'inventory_item_id'),
        db.Index('ix_extra_batch_consumable_organization_id', 'organization_id'),
    )
