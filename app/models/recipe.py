
import os
from flask_login import current_user
from ..extensions import db
import sqlalchemy as sa
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

# Dialect-aware helpers: enable Postgres-only computed columns and indexes
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

def _pg_computed(expr: str):
    return sa.Computed(expr, persisted=True) if _IS_PG else None

class Recipe(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    instructions = db.Column(db.Text)
    label_prefix = db.Column(db.String(8))
    qr_image = db.Column(db.String(128))
    parent_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    cloned_from_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    root_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    is_locked = db.Column(db.Boolean, default=False)
    predicted_yield = db.Column(db.Float, default=0.0)
    predicted_yield_unit = db.Column(db.String(50), default="oz")
    allowed_containers = db.Column(db.PickleType, default=list)
    category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    product_category = db.relationship('ProductCategory')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # Timestamps for retention calculations
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)
    parent = db.relationship(
        'Recipe',
        remote_side=[id],
        foreign_keys=[parent_recipe_id],
        backref='variations',
        primaryjoin="Recipe.parent_recipe_id==Recipe.id"
    )
    cloned_from = db.relationship(
        'Recipe',
        remote_side=[id],
        foreign_keys=[cloned_from_id],
        backref='clones',
        primaryjoin="Recipe.cloned_from_id==Recipe.id"
    )
    root_recipe = db.relationship(
        'Recipe',
        remote_side=[id],
        foreign_keys=[root_recipe_id],
        backref='lineage_descendants',
        primaryjoin="Recipe.root_recipe_id==Recipe.id"
    )
    recipe_ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")
    # Consumables used during production (e.g., gloves, filters). Snapshot at batch start.
    recipe_consumables = db.relationship('RecipeConsumable', backref='recipe', cascade="all, delete-orphan")
    portioning_data = db.Column(db.JSON, nullable=True)
    # Absolute additive columns for clarity
    is_portioned = db.Column(db.Boolean, nullable=True)
    portion_name = db.Column(db.String(64), nullable=True)
    portion_count = db.Column(db.Integer, nullable=True)
    portion_unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)
    # Category-specific structured fields (per-category aids, e.g., lye settings, fragrance load, phases)
    category_data = db.Column(db.JSON, nullable=True)

    # Computed projection columns (persisted) for hot fields (Postgres only)
    soap_superfat = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'soap_superfat'))::numeric"), nullable=True)
    soap_water_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'soap_water_pct'))::numeric"), nullable=True)
    soap_lye_type = db.Column(sa.Text(), _pg_computed("(category_data ->> 'soap_lye_type')"), nullable=True)

    candle_fragrance_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'candle_fragrance_pct'))::numeric"), nullable=True)
    candle_vessel_ml = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'candle_vessel_ml'))::numeric"), nullable=True)
    vessel_fill_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'vessel_fill_pct'))::numeric"), nullable=True)

    baker_base_flour_g = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'baker_base_flour_g'))::numeric"), nullable=True)
    baker_water_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'baker_water_pct'))::numeric"), nullable=True)
    baker_salt_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'baker_salt_pct'))::numeric"), nullable=True)
    baker_yeast_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'baker_yeast_pct'))::numeric"), nullable=True)

    cosm_emulsifier_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'cosm_emulsifier_pct'))::numeric"), nullable=True)
    cosm_preservative_pct = db.Column(sa.Numeric(), _pg_computed("((category_data ->> 'cosm_preservative_pct'))::numeric"), nullable=True)

    # Performance indexes and org scoping
    # Indexes; include Postgres-only JSONB GIN index conditionally
    __table_args__ = tuple([
        db.Index('ix_recipe_org', 'organization_id'),
        db.Index('ix_recipe_category_id', 'category_id'),
        db.Index('ix_recipe_parent_recipe_id', 'parent_recipe_id'),
        db.Index('ix_recipe_cloned_from_id', 'cloned_from_id'),
        db.Index('ix_recipe_root_recipe_id', 'root_recipe_id'),
        *([db.Index('ix_recipe_category_data_gin', db.text('(category_data::jsonb)'), postgresql_using='gin')] if _IS_PG else []),
        db.Index('ix_recipe_soap_superfat', 'soap_superfat'),
        db.Index('ix_recipe_soap_water_pct', 'soap_water_pct'),
        db.Index('ix_recipe_soap_lye_type', 'soap_lye_type'),
        db.Index('ix_recipe_candle_fragrance_pct', 'candle_fragrance_pct'),
        db.Index('ix_recipe_candle_vessel_ml', 'candle_vessel_ml'),
        db.Index('ix_recipe_vessel_fill_pct', 'vessel_fill_pct'),
        db.Index('ix_recipe_baker_base_flour_g', 'baker_base_flour_g'),
        db.Index('ix_recipe_baker_water_pct', 'baker_water_pct'),
        db.Index('ix_recipe_baker_salt_pct', 'baker_salt_pct'),
        db.Index('ix_recipe_baker_yeast_pct', 'baker_yeast_pct'),
        db.Index('ix_recipe_cosm_emulsifier_pct', 'cosm_emulsifier_pct'),
        db.Index('ix_recipe_cosm_preservative_pct', 'cosm_preservative_pct'),
    ])

class RecipeIngredient(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    notes = db.Column(db.Text)
    order_position = db.Column(db.Integer, default=0)

    inventory_item = db.relationship('InventoryItem', backref='recipe_usages')


class RecipeConsumable(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe_consumable'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    notes = db.Column(db.Text)
    order_position = db.Column(db.Integer, default=0)

    inventory_item = db.relationship('InventoryItem', backref='recipe_consumable_usages')

# Defensive defaulting: ensure a category is assigned if omitted in code paths
from sqlalchemy import event

@event.listens_for(Recipe, "before_insert")
def _assign_default_category_before_insert(mapper, connection, target):
    """Assign a default ProductCategory if none was provided.

    This preserves the NOT NULL invariant while keeping programmatic creations
    (e.g., tests or scripts) from violating constraints when category is omitted.
    """
    try:
        if getattr(target, 'category_id', None) is None:
            from .product_category import ProductCategory
            from ..extensions import db
            default_cat = ProductCategory.query.filter_by(name='Uncategorized').first()
            if not default_cat:
                default_cat = ProductCategory(name='Uncategorized')
                db.session.add(default_cat)
                db.session.flush()
            target.category_id = default_cat.id
    except Exception:
        # As a last resort, do nothing and let DB raise if truly impossible
        pass


class RecipeLineage(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe_lineage'

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    source_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    event_type = db.Column(db.String(32), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)

    recipe = db.relationship('Recipe', foreign_keys=[recipe_id], backref='lineage_events')
    source_recipe = db.relationship('Recipe', foreign_keys=[source_recipe_id], backref='lineage_source_events', viewonly=True)
