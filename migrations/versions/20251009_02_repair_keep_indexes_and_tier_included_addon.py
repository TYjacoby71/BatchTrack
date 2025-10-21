"""
Repair keep-list indexes/tables and add tier_included_addon

Revision ID: 20251009_2
Revises: 20251009_1
Create Date: 2025-10-09

This migration is defensive and idempotent. It will:
- Create association table tier_included_addon if missing
- Ensure org-scoping indexes exist (user, inventory_item, inventory_lot, unified_inventory_history, recipe, batch)
- Ensure global_item_alias table exists with its indexes
- Ensure JSON/GIN indexes on recipe.category_data and global_item.aka_names
- Ensure recipe/batch generated “category extension” columns and their indexes exist
- Ensure ix_product_category_id and a functional unique index on product_category lower(name)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '20251009_2'
down_revision = '20251009_1'
branch_labels = None
depends_on = None


# Helper utilities

def table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        cols = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def index_exists(table_name: str, index_name: str) -> bool:
    # Try pg_indexes fast path; fall back to inspector
    try:
        bind = op.get_bind()
        try:
            result = bind.execute(text(
                """
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE tablename = :table_name
                  AND indexname = :index_name
                """
            ), {"table_name": table_name, "index_name": index_name})
            return result.scalar() > 0
        except Exception:
            inspector = inspect(bind)
            idxs = inspector.get_indexes(table_name)
            return any(i.get('name') == index_name for i in idxs)
    except Exception:
        return False


def safe_create_index(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if not table_exists(table_name):
        return
    if index_exists(table_name, index_name):
        return
    try:
        op.create_index(index_name, table_name, columns, unique=unique)
    except Exception:
        # Ignore on unsupported backends or conflicts
        pass


# Feature helpers

def create_tier_included_addon_if_missing() -> None:
    if table_exists('tier_included_addon'):
        return
    if not table_exists('subscription_tier') or not table_exists('addon'):
        # Required tables missing; skip safely
        return
    op.create_table(
        'tier_included_addon',
        sa.Column('tier_id', sa.Integer(), nullable=False),
        sa.Column('addon_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tier_id'], ['subscription_tier.id']),
        sa.ForeignKeyConstraint(['addon_id'], ['addon.id']),
        sa.PrimaryKeyConstraint('tier_id', 'addon_id'),
    )


def create_tier_allowed_addon_if_missing() -> None:
    """Ensure the association table expected by models exists.

    Models reference `tier_allowed_addon` for the allowed add-ons relationship.
    This migration predates that table, so create it defensively here to avoid
    runtime errors in environments where subsequent migrations have not yet run.
    """
    if table_exists('tier_allowed_addon'):
        return
    if not table_exists('subscription_tier') or not table_exists('addon'):
        return
    op.create_table(
        'tier_allowed_addon',
        sa.Column('tier_id', sa.Integer(), nullable=False),
        sa.Column('addon_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tier_id'], ['subscription_tier.id']),
        sa.ForeignKeyConstraint(['addon_id'], ['addon.id']),
        sa.PrimaryKeyConstraint('tier_id', 'addon_id'),
    )


def ensure_org_scoping_indexes() -> None:
    targets = [
        ('user', 'organization_id', 'ix_user_org'),
        ('inventory_item', 'organization_id', 'ix_inventory_item_org'),
        ('inventory_lot', 'organization_id', 'ix_inventory_lot_org'),
        ('unified_inventory_history', 'organization_id', 'ix_unified_history_org'),
        ('recipe', 'organization_id', 'ix_recipe_org'),
        ('batch', 'organization_id', 'ix_batch_org'),
    ]
    for table, col, ix in targets:
        safe_create_index(ix, table, [col], unique=False)


def ensure_global_item_alias_and_indexes() -> None:
    # Table is created in 20250930_01; do not recreate here.
    if not table_exists('global_item_alias'):
        return
    # Indexes (btree)
    safe_create_index('ix_global_item_alias_alias', 'global_item_alias', ['alias'])
    safe_create_index('ix_global_item_alias_global_item_id', 'global_item_alias', ['global_item_id'])
    # GIN index on tsvector (PostgreSQL only)
    try:
        op.execute("CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias USING GIN (to_tsvector('simple', alias))")
    except Exception:
        pass


def ensure_json_gin_indexes() -> None:
    # recipe.category_data
    if table_exists('recipe'):
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING GIN ((category_data::jsonb))")
        except Exception:
            pass
    # global_item.aka_names
    if table_exists('global_item'):
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING GIN ((aka_names::jsonb))")
        except Exception:
            pass


def _add_generated_or_backfilled_column_recipe(col_name: str, sql_type: str, json_key: str, cast: str | None = None) -> None:
    if not table_exists('recipe') or column_exists('recipe', col_name):
        return
    cast_expr = f"::{cast}" if cast else ""
    gen_expr = f"(category_data->>'{json_key}'){cast_expr}"
    ddl = f"ALTER TABLE recipe ADD COLUMN {col_name} {sql_type} GENERATED ALWAYS AS ({gen_expr}) STORED"
    try:
        op.execute(ddl)
    except Exception:
        # Fallback: regular nullable column + best-effort backfill
        with op.batch_alter_table('recipe') as batch_op:
            if sql_type.lower() == 'text':
                batch_op.add_column(sa.Column(col_name, sa.Text(), nullable=True))
            else:
                batch_op.add_column(sa.Column(col_name, sa.Numeric(), nullable=True))
        try:
            backfill_sql = (
                f"UPDATE recipe SET {col_name} = NULLIF(category_data->>'{json_key}', '')"
            )
            if sql_type.lower() != 'text':
                backfill_sql += "::numeric"
            backfill_sql += " WHERE category_data IS NOT NULL"
            op.execute(backfill_sql)
        except Exception:
            pass


def _add_generated_or_backfilled_column_batch(col_name: str, sql_type: str, json_path: str) -> None:
    if not table_exists('batch') or column_exists('batch', col_name):
        return
    parts = json_path.split('.') if json_path else []
    expr = 'plan_snapshot'
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            expr += f"->'{part}'"
        else:
            expr += f"->>'{part}'"
    is_text = (sql_type.lower() == 'text')
    cast_expr = '' if is_text else '::numeric'
    ddl = f"ALTER TABLE batch ADD COLUMN {col_name} {sql_type} GENERATED ALWAYS AS (({expr}){cast_expr}) STORED"
    try:
        op.execute(ddl)
    except Exception:
        with op.batch_alter_table('batch') as batch_op:
            if is_text:
                batch_op.add_column(sa.Column(col_name, sa.Text(), nullable=True))
            else:
                batch_op.add_column(sa.Column(col_name, sa.Numeric(), nullable=True))
        try:
            backfill_sql = f"""
                UPDATE batch
                SET {col_name} = NULLIF({expr}, ''){cast_expr}
                WHERE plan_snapshot IS NOT NULL
            """
            op.execute(backfill_sql)
        except Exception:
            pass


def ensure_recipe_batch_generated_columns_and_indexes() -> None:
    # Recipe: numeric fields
    numeric_fields = [
        ('soap_superfat', 'numeric', 'soap_superfat', 'numeric'),
        ('soap_water_pct', 'numeric', 'soap_water_pct', 'numeric'),
        ('candle_fragrance_pct', 'numeric', 'candle_fragrance_pct', 'numeric'),
        ('candle_vessel_ml', 'numeric', 'candle_vessel_ml', 'numeric'),
        ('vessel_fill_pct', 'numeric', 'vessel_fill_pct', 'numeric'),
        ('baker_base_flour_g', 'numeric', 'baker_base_flour_g', 'numeric'),
        ('baker_water_pct', 'numeric', 'baker_water_pct', 'numeric'),
        ('baker_salt_pct', 'numeric', 'baker_salt_pct', 'numeric'),
        ('baker_yeast_pct', 'numeric', 'baker_yeast_pct', 'numeric'),
        ('cosm_emulsifier_pct', 'numeric', 'cosm_emulsifier_pct', 'numeric'),
        ('cosm_preservative_pct', 'numeric', 'cosm_preservative_pct', 'numeric'),
    ]
    for col_name, sql_type, json_key, cast in numeric_fields:
        _add_generated_or_backfilled_column_recipe(col_name, sql_type, json_key, cast)
    _add_generated_or_backfilled_column_recipe('soap_lye_type', 'text', 'soap_lye_type', None)

    # Recipe indexes
    ix_targets_recipe = [
        'soap_superfat', 'soap_water_pct', 'soap_lye_type',
        'candle_fragrance_pct', 'candle_vessel_ml', 'vessel_fill_pct',
        'baker_base_flour_g', 'baker_water_pct', 'baker_salt_pct', 'baker_yeast_pct',
        'cosm_emulsifier_pct', 'cosm_preservative_pct',
    ]
    for col in ix_targets_recipe:
        safe_create_index(f'ix_recipe_{col}', 'recipe', [col])

    # Batch: numeric fields
    numeric_mappings = [
        ('vessel_fill_pct', 'numeric', 'category_extension.vessel_fill_pct'),
        ('candle_fragrance_pct', 'numeric', 'category_extension.candle_fragrance_pct'),
        ('candle_vessel_ml', 'numeric', 'category_extension.candle_vessel_ml'),
        ('soap_superfat', 'numeric', 'category_extension.soap_superfat'),
        ('soap_water_pct', 'numeric', 'category_extension.soap_water_pct'),
        ('baker_base_flour_g', 'numeric', 'category_extension.baker_base_flour_g'),
        ('baker_water_pct', 'numeric', 'category_extension.baker_water_pct'),
        ('baker_salt_pct', 'numeric', 'category_extension.baker_salt_pct'),
        ('baker_yeast_pct', 'numeric', 'category_extension.baker_yeast_pct'),
        ('cosm_emulsifier_pct', 'numeric', 'category_extension.cosm_emulsifier_pct'),
        ('cosm_preservative_pct', 'numeric', 'category_extension.cosm_preservative_pct'),
    ]
    for col_name, sql_type, json_path in numeric_mappings:
        _add_generated_or_backfilled_column_batch(col_name, sql_type, json_path)
    _add_generated_or_backfilled_column_batch('soap_lye_type', 'text', 'category_extension.soap_lye_type')

    # Batch indexes
    ix_targets_batch = [
        'vessel_fill_pct', 'candle_fragrance_pct', 'candle_vessel_ml',
        'soap_superfat', 'soap_water_pct', 'soap_lye_type',
        'baker_base_flour_g', 'baker_water_pct', 'baker_salt_pct', 'baker_yeast_pct',
        'cosm_emulsifier_pct', 'cosm_preservative_pct',
    ]
    for col in ix_targets_batch:
        safe_create_index(f'ix_batch_{col}', 'batch', [col])


def ensure_product_category_indexes() -> None:
    # product.category_id btree index
    safe_create_index('ix_product_category_id', 'product', ['category_id'])
    # product_category lower(name) unique functional index (PostgreSQL only)
    if table_exists('product_category'):
        try:
            op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name))")
        except Exception:
            pass


def upgrade():
    create_tier_included_addon_if_missing()
    create_tier_allowed_addon_if_missing()
    ensure_org_scoping_indexes()
    ensure_global_item_alias_and_indexes()
    ensure_json_gin_indexes()
    ensure_recipe_batch_generated_columns_and_indexes()
    ensure_product_category_indexes()


def downgrade():
    # Best-effort reversals for objects this migration introduced directly
    # Drop functional product_category index
    try:
        op.execute("DROP INDEX IF EXISTS ix_product_category_lower_name")
    except Exception:
        pass

    # Tier association table
    if table_exists('tier_included_addon'):
        try:
            op.drop_table('tier_included_addon')
        except Exception:
            pass
    if table_exists('tier_allowed_addon'):
        try:
            op.drop_table('tier_allowed_addon')
        except Exception:
            pass

    # Non-destructive: keep org indexes, global_item_alias, and GIN indexes since
    # they are part of the performance baseline and may be relied upon by earlier revisions.
    pass
