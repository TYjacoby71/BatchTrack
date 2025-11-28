
from flask_login import current_user
from ..extensions import db
import sqlalchemy as sa
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils
from .db_dialect import is_postgres

_IS_PG = is_postgres()

def _pg_computed(expr: str):
    return sa.Computed(expr, persisted=True) if _IS_PG else None

class Batch(ScopedModelMixin, db.Model):
    __tablename__ = 'batch'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    label_code = db.Column(db.String(32))
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

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'label_code', name='uq_batch_org_label'),
        db.Index('ix_batch_org', 'organization_id'),
        db.Index('ix_batch_vessel_fill_pct', 'vessel_fill_pct'),
        db.Index('ix_batch_candle_fragrance_pct', 'candle_fragrance_pct'),
        db.Index('ix_batch_candle_vessel_ml', 'candle_vessel_ml'),
        db.Index('ix_batch_soap_superfat', 'soap_superfat'),
        db.Index('ix_batch_soap_water_pct', 'soap_water_pct'),
        db.Index('ix_batch_soap_lye_type', 'soap_lye_type'),
        db.Index('ix_batch_baker_base_flour_g', 'baker_base_flour_g'),
        db.Index('ix_batch_baker_water_pct', 'baker_water_pct'),
        db.Index('ix_batch_baker_salt_pct', 'baker_salt_pct'),
        db.Index('ix_batch_baker_yeast_pct', 'baker_yeast_pct'),
        db.Index('ix_batch_cosm_emulsifier_pct', 'cosm_emulsifier_pct'),
        db.Index('ix_batch_cosm_preservative_pct', 'cosm_preservative_pct'),
    )

    # Computed projection columns (persisted) for hot fields from plan_snapshot.category_extension (Postgres only)
    vessel_fill_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'vessel_fill_pct'))::numeric"), nullable=True)
    candle_fragrance_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'candle_fragrance_pct'))::numeric"), nullable=True)
    candle_vessel_ml = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'candle_vessel_ml'))::numeric"), nullable=True)
    soap_superfat = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'soap_superfat'))::numeric"), nullable=True)
    soap_water_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'soap_water_pct'))::numeric"), nullable=True)
    soap_lye_type = db.Column(sa.Text(), _pg_computed("((plan_snapshot -> 'category_extension') ->> 'soap_lye_type')"), nullable=True)
    baker_base_flour_g = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'baker_base_flour_g'))::numeric"), nullable=True)
    baker_water_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'baker_water_pct'))::numeric"), nullable=True)
    baker_salt_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'baker_salt_pct'))::numeric"), nullable=True)
    baker_yeast_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'baker_yeast_pct'))::numeric"), nullable=True)
    cosm_emulsifier_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'cosm_emulsifier_pct'))::numeric"), nullable=True)
    cosm_preservative_pct = db.Column(sa.Numeric(), _pg_computed("(((plan_snapshot -> 'category_extension') ->> 'cosm_preservative_pct'))::numeric"), nullable=True)

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
