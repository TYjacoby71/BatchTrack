from flask_login import current_user
import sqlalchemy as sa
from sqlalchemy import event

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
from .db_dialect import is_postgres
from .mixins import ScopedModelMixin
from app.services.cache_invalidation import (
    invalidate_recipe_list_cache,
    invalidate_public_recipe_library_cache,
)

_IS_PG = is_postgres()

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
    status = db.Column(db.String(16), default='published', nullable=False, server_default='published')
    sharing_scope = db.Column(db.String(16), nullable=False, default='private', server_default='private')
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
    moderation_events = db.relationship('RecipeModerationEvent', backref='recipe', cascade="all, delete-orphan")
    portioning_data = db.Column(db.JSON, nullable=True)
    # Absolute additive columns for clarity
    is_portioned = db.Column(db.Boolean, nullable=True)
    portion_name = db.Column(db.String(64), nullable=True)
    portion_count = db.Column(db.Integer, nullable=True)
    portion_unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)
    # Category-specific structured fields (per-category aids, e.g., lye settings, fragrance load, phases)
    category_data = db.Column(db.JSON, nullable=True)

    # Marketplace / Library metadata
    is_public = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("false"))
    is_for_sale = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("false"))
    sale_price = db.Column(sa.Numeric(12, 4), nullable=True)
    is_sellable = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.text("true"))
    marketplace_status = db.Column(db.String(32), nullable=False, default='draft', server_default='draft')
    marketplace_notes = db.Column(db.Text, nullable=True)
    marketplace_violation_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    marketplace_blocked = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("false"))
    public_description = db.Column(db.Text, nullable=True)
    product_store_url = db.Column(db.String(512), nullable=True)
    shopify_product_url = db.Column(db.String(512), nullable=True)
    cover_image_path = db.Column(db.String(255), nullable=True)
    cover_image_url = db.Column(db.String(512), nullable=True)
    skin_opt_in = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.text("true"))
    origin_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    origin_organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    download_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    purchase_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')

    # Organization origin fields (from migration 0013)
    org_origin_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    org_origin_type = db.Column(db.String(32), nullable=False, default='authored', server_default='authored')
    org_origin_source_org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    org_origin_source_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    org_origin_purchased = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("false"))
    is_sellable = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.text("true"))

    organization = db.relationship('Organization', foreign_keys='Recipe.organization_id')
    origin_recipe = db.relationship(
        'Recipe',
        remote_side=[id],
        foreign_keys=[origin_recipe_id],
        post_update=True,
        backref='referenced_descendants',
    )
    origin_organization = db.relationship('Organization', foreign_keys=[origin_organization_id])
    org_origin_recipe = db.relationship(
        'Recipe',
        remote_side=[id],
        foreign_keys=[org_origin_recipe_id],
        post_update=True,
    )
    org_origin_source_org = db.relationship('Organization', foreign_keys=[org_origin_source_org_id])
    org_origin_source_recipe = db.relationship(
        'Recipe',
        remote_side=[id],
        foreign_keys=[org_origin_source_recipe_id],
        post_update=True,
    )

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
        db.Index('ix_recipe_sharing_scope', 'sharing_scope'),
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
        db.Index('ix_recipe_is_public', 'is_public'),
        db.Index('ix_recipe_is_for_sale', 'is_for_sale'),
        db.Index('ix_recipe_marketplace_status', 'marketplace_status'),
        db.Index('ix_recipe_is_sellable', 'is_sellable'),
        db.Index('ix_recipe_product_store_url', 'product_store_url'),
        db.Index('ix_recipe_origin_recipe_id', 'origin_recipe_id'),
        db.Index('ix_recipe_origin_organization_id', 'origin_organization_id'),
        db.Index('ix_recipe_download_count', 'download_count'),
        db.Index('ix_recipe_purchase_count', 'purchase_count'),
        db.Index('ix_recipe_org_origin_recipe_id', 'org_origin_recipe_id'),
        db.Index('ix_recipe_org_origin_type', 'org_origin_type'),
        db.Index('ix_recipe_org_origin_source_org_id', 'org_origin_source_org_id'),
        db.Index('ix_recipe_org_origin_purchased', 'org_origin_purchased'),
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


def _invalidate_recipe_caches(org_id: int | None) -> None:
    if org_id:
        invalidate_recipe_list_cache(org_id)
    invalidate_public_recipe_library_cache()


def _lookup_recipe_org(connection, recipe_id: int | None):
    if not recipe_id:
        return None
    recipe_tbl = Recipe.__table__
    row = connection.execute(
        recipe_tbl.select()
        .with_only_columns(recipe_tbl.c.organization_id)
        .where(recipe_tbl.c.id == recipe_id)
    ).first()
    return row[0] if row else None


@event.listens_for(RecipeIngredient, "after_insert")
def _recipe_ingredient_after_insert(mapper, connection, target):
    org_id = _lookup_recipe_org(connection, getattr(target, "recipe_id", None))
    _invalidate_recipe_caches(org_id)


@event.listens_for(RecipeIngredient, "after_delete")
def _recipe_ingredient_after_delete(mapper, connection, target):
    org_id = _lookup_recipe_org(connection, getattr(target, "recipe_id", None))
    _invalidate_recipe_caches(org_id)


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


@event.listens_for(Recipe, "after_insert")
def _recipe_after_insert(mapper, connection, target):
    org_id = getattr(target, "organization_id", None)
    _invalidate_recipe_caches(org_id)


@event.listens_for(Recipe, "after_update")
def _recipe_after_update(mapper, connection, target):
    org_id = getattr(target, "organization_id", None)
    _invalidate_recipe_caches(org_id)


@event.listens_for(Recipe, "after_delete")
def _recipe_after_delete(mapper, connection, target):
    org_id = getattr(target, "organization_id", None)
    _invalidate_recipe_caches(org_id)


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

    __table_args__ = (
        db.Index('ix_recipe_lineage_recipe_id', 'recipe_id'),
        db.Index('ix_recipe_lineage_source_recipe_id', 'source_recipe_id'),
        db.Index('ix_recipe_lineage_event_type', 'event_type'),
    )