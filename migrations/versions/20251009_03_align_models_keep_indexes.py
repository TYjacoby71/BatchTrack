"""
Align models to own keep-list indexes, projections, and association table

Revision ID: 20251009_3
Revises: 20251009_2
Create Date: 2025-10-09

This revision is auto-written to reflect model-owned objects so Alembic
autogenerate won't propose drops. It is defensive and idempotent.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy import inspect

revision = '20251009_3'
down_revision = '20251009_2'
branch_labels = None
depends_on = None


def table_exists(inspector, table_name: str) -> bool:
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not table_exists(inspector, table_name):
        return False
    try:
        cols = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def index_exists(bind, index_name: str) -> bool:
    try:
        res = bind.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM pg_class c 
                JOIN pg_namespace n ON n.oid = c.relnamespace 
                WHERE c.relname = :index_name AND c.relkind = 'i'
            )
        """), {"index_name": index_name})
        return bool(res.scalar())
    except Exception:
        return False


def create_index_if_missing(bind, table_name: str, index_name: str, columns: list[str], unique: bool = False):
    if index_exists(bind, index_name):
        return
    try:
        op.create_index(index_name, table_name, columns, unique=unique)
    except Exception:
        pass


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1) Org-scoping indexes
    for table, col, ix in [
        ('user', 'organization_id', 'ix_user_org'),
        ('inventory_item', 'organization_id', 'ix_inventory_item_org'),
        ('inventory_lot', 'organization_id', 'ix_inventory_lot_org'),
        ('unified_inventory_history', 'organization_id', 'ix_unified_history_org'),
        ('recipe', 'organization_id', 'ix_recipe_org'),
        ('batch', 'organization_id', 'ix_batch_org'),
    ]:
        if table_exists(inspector, table):
            create_index_if_missing(bind, table, ix, [col], unique=False)

    # 2) ProductCategory functional unique index
    if table_exists(inspector, 'product_category'):
        try:
            bind.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name::text))"))
        except Exception:
            pass

    # 3) Product foreign key index
    if table_exists(inspector, 'product'):
        create_index_if_missing(bind, 'product', 'ix_product_category_id', ['category_id'], unique=False)

    # 4) Recipe computed columns and indexes
    if table_exists(inspector, 'recipe'):
        # Computed columns - add if missing
        computed_cols = {
            'soap_superfat': "((category_data ->> 'soap_superfat'))::numeric",
            'soap_water_pct': "((category_data ->> 'soap_water_pct'))::numeric",
            'soap_lye_type': "(category_data ->> 'soap_lye_type')",
            'candle_fragrance_pct': "((category_data ->> 'candle_fragrance_pct'))::numeric",
            'candle_vessel_ml': "((category_data ->> 'candle_vessel_ml'))::numeric",
            'vessel_fill_pct': "((category_data ->> 'vessel_fill_pct'))::numeric",
            'baker_base_flour_g': "((category_data ->> 'baker_base_flour_g'))::numeric",
            'baker_water_pct': "((category_data ->> 'baker_water_pct'))::numeric",
            'baker_salt_pct': "((category_data ->> 'baker_salt_pct'))::numeric",
            'baker_yeast_pct': "((category_data ->> 'baker_yeast_pct'))::numeric",
            'cosm_emulsifier_pct': "((category_data ->> 'cosm_emulsifier_pct'))::numeric",
            'cosm_preservative_pct': "((category_data ->> 'cosm_preservative_pct'))::numeric",
        }
        for name, expr in computed_cols.items():
            if not column_exists(inspector, 'recipe', name):
                try:
                    op.execute(f"ALTER TABLE recipe ADD COLUMN {name} "
                               + ("text" if name.endswith('_type') else "numeric")
                               + f" GENERATED ALWAYS AS ({expr}) STORED")
                except Exception:
                    # Fallback to nullable column
                    if name.endswith('_type'):
                        op.add_column('recipe', sa.Column(name, sa.Text(), nullable=True))
                    else:
                        op.add_column('recipe', sa.Column(name, sa.Numeric(), nullable=True))
        # Indexes
        for ix, col in [
            ('ix_recipe_category_id', 'category_id'),
            ('ix_recipe_soap_superfat', 'soap_superfat'),
            ('ix_recipe_soap_water_pct', 'soap_water_pct'),
            ('ix_recipe_soap_lye_type', 'soap_lye_type'),
            ('ix_recipe_candle_fragrance_pct', 'candle_fragrance_pct'),
            ('ix_recipe_candle_vessel_ml', 'candle_vessel_ml'),
            ('ix_recipe_vessel_fill_pct', 'vessel_fill_pct'),
            ('ix_recipe_baker_base_flour_g', 'baker_base_flour_g'),
            ('ix_recipe_baker_water_pct', 'baker_water_pct'),
            ('ix_recipe_baker_salt_pct', 'baker_salt_pct'),
            ('ix_recipe_baker_yeast_pct', 'baker_yeast_pct'),
            ('ix_recipe_cosm_emulsifier_pct', 'cosm_emulsifier_pct'),
            ('ix_recipe_cosm_preservative_pct', 'cosm_preservative_pct'),
        ]:
            create_index_if_missing(bind, 'recipe', ix, [col])
        # JSON/GIN
        try:
            bind.execute(text("CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING GIN ((category_data::jsonb))"))
        except Exception:
            pass

    # 5) Batch computed columns and indexes
    if table_exists(inspector, 'batch'):
        computed_cols = {
            'vessel_fill_pct': "(((plan_snapshot -> 'category_extension') ->> 'vessel_fill_pct'))::numeric",
            'candle_fragrance_pct': "(((plan_snapshot -> 'category_extension') ->> 'candle_fragrance_pct'))::numeric",
            'candle_vessel_ml': "(((plan_snapshot -> 'category_extension') ->> 'candle_vessel_ml'))::numeric",
            'soap_superfat': "(((plan_snapshot -> 'category_extension') ->> 'soap_superfat'))::numeric",
            'soap_water_pct': "(((plan_snapshot -> 'category_extension') ->> 'soap_water_pct'))::numeric",
            'soap_lye_type': "((plan_snapshot -> 'category_extension') ->> 'soap_lye_type')",
            'baker_base_flour_g': "(((plan_snapshot -> 'category_extension') ->> 'baker_base_flour_g'))::numeric",
            'baker_water_pct': "(((plan_snapshot -> 'category_extension') ->> 'baker_water_pct'))::numeric",
            'baker_salt_pct': "(((plan_snapshot -> 'category_extension') ->> 'baker_salt_pct'))::numeric",
            'baker_yeast_pct': "(((plan_snapshot -> 'category_extension') ->> 'baker_yeast_pct'))::numeric",
            'cosm_emulsifier_pct': "(((plan_snapshot -> 'category_extension') ->> 'cosm_emulsifier_pct'))::numeric",
            'cosm_preservative_pct': "(((plan_snapshot -> 'category_extension') ->> 'cosm_preservative_pct'))::numeric",
        }
        for name, expr in computed_cols.items():
            if not column_exists(inspector, 'batch', name):
                try:
                    op.execute(f"ALTER TABLE batch ADD COLUMN {name} "
                               + ("text" if name.endswith('_type') else "numeric")
                               + f" GENERATED ALWAYS AS ({expr}) STORED")
                except Exception:
                    if name.endswith('_type'):
                        op.add_column('batch', sa.Column(name, sa.Text(), nullable=True))
                    else:
                        op.add_column('batch', sa.Column(name, sa.Numeric(), nullable=True))
        for ix, col in [
            ('ix_batch_vessel_fill_pct', 'vessel_fill_pct'),
            ('ix_batch_candle_fragrance_pct', 'candle_fragrance_pct'),
            ('ix_batch_candle_vessel_ml', 'candle_vessel_ml'),
            ('ix_batch_soap_superfat', 'soap_superfat'),
            ('ix_batch_soap_water_pct', 'soap_water_pct'),
            ('ix_batch_soap_lye_type', 'soap_lye_type'),
            ('ix_batch_baker_base_flour_g', 'baker_base_flour_g'),
            ('ix_batch_baker_water_pct', 'baker_water_pct'),
            ('ix_batch_baker_salt_pct', 'baker_salt_pct'),
            ('ix_batch_baker_yeast_pct', 'baker_yeast_pct'),
            ('ix_batch_cosm_emulsifier_pct', 'cosm_emulsifier_pct'),
            ('ix_batch_cosm_preservative_pct', 'cosm_preservative_pct'),
        ]:
            create_index_if_missing(bind, 'batch', ix, [col])

    # 6) BatchConsumable & ExtraBatchConsumable indexes
    for table, indexes in [
        ('batch_consumable', [
            ('ix_batch_consumable_batch_id', 'batch_id'),
            ('ix_batch_consumable_inventory_item_id', 'inventory_item_id'),
            ('ix_batch_consumable_organization_id', 'organization_id'),
        ]),
        ('extra_batch_consumable', [
            ('ix_extra_batch_consumable_batch_id', 'batch_id'),
            ('ix_extra_batch_consumable_inventory_item_id', 'inventory_item_id'),
            ('ix_extra_batch_consumable_organization_id', 'organization_id'),
        ]),
    ]:
        if table_exists(inspector, table):
            for ix, col in indexes:
                create_index_if_missing(bind, table, ix, [col])

    # 7) Global Item alias table and indexes
    if not table_exists(inspector, 'global_item_alias') and table_exists(inspector, 'global_item'):
        op.create_table(
            'global_item_alias',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
            sa.Column('alias', sa.Text(), nullable=False),
        )
    if table_exists(inspector, 'global_item_alias'):
        create_index_if_missing(bind, 'global_item_alias', 'ix_global_item_alias_alias', ['alias'])
        create_index_if_missing(bind, 'global_item_alias', 'ix_global_item_alias_global_item_id', ['global_item_id'])
        try:
            bind.execute(text("CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias USING GIN (to_tsvector('simple', alias))"))
        except Exception:
            pass

    # 8) GlobalItem aka_names JSON/GIN
    if table_exists(inspector, 'global_item'):
        try:
            bind.execute(text("CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING GIN ((aka_names::jsonb))"))
        except Exception:
            pass


def downgrade():
    # No destructive downgrades; these are model-owned performance objects.
    pass
