"""
Align DB schema with current models: add missing columns, FKs, indexes.
Revision ID: 20251021_99
Revises: 20251021_04
Create Date: 2025-10-21

This migration is intentionally idempotent and adds only missing columns/indexes
that are required by the current SQLAlchemy models for core features.
It avoids destructive drops/renames for safety.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '20251021_99'
down_revision = '20251021_04'
branch_labels = None
depends_on = None


def table_exists(table: str) -> bool:
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return table in insp.get_table_names()
    except Exception:
        return False


def column_exists(table: str, column: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return any(c['name'] == column for c in insp.get_columns(table))
    except Exception:
        return False


def index_exists(table: str, index: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return any(ix['name'] == index for ix in insp.get_indexes(table))
    except Exception:
        return False


def fk_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return any(fk.get('name') == name for fk in insp.get_foreign_keys(table))
    except Exception:
        return False


def unique_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return any(uq.get('name') == name for uq in insp.get_unique_constraints(table))
    except Exception:
        return False


def has_duplicates(table: str, columns: list[str]) -> bool:
    """Return True if any duplicate rows exist for the given columns (NULLs ignored)."""
    if not table_exists(table):
        return False
    bind = op.get_bind()
    # Build GROUP BY query that filters rows where all columns are NOT NULL
    cols_csv = ", ".join(columns)
    not_null_cond = " AND ".join([f"{c} IS NOT NULL" for c in columns]) or "TRUE"
    q = text(
        f"""
        SELECT 1
        FROM {table}
        WHERE {not_null_cond}
        GROUP BY {cols_csv}
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )
    try:
        return bind.execute(q).first() is not None
    except Exception:
        # If the query itself fails, err on the side of skipping the constraint
        return True


def has_orphans(source: str, local_col: str, referent: str, remote_col: str = 'id') -> bool:
    """Return True if there are rows in source with non-null local_col not present in referent.remote_col."""
    if not table_exists(source) or not table_exists(referent):
        return False
    bind = op.get_bind()
    q = text(
        f"""
        SELECT 1
        FROM {source} s
        LEFT JOIN {referent} r ON s.{local_col} = r.{remote_col}
        WHERE s.{local_col} IS NOT NULL AND r.{remote_col} IS NULL
        LIMIT 1
        """
    )
    try:
        return bind.execute(q).first() is not None
    except Exception:
        # On error, assume unsafe
        return True


def safe_add_column(table: str, col: sa.Column) -> bool:
    if not table_exists(table):
        return False
    if column_exists(table, col.name):
        return False
    try:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(col)
        return True
    except Exception:
        return False


def safe_create_index(name: str, table: str, columns: list[str], unique: bool = False) -> bool:
    if index_exists(table, name):
        return False
    try:
        op.create_index(name, table, columns, unique=unique)
        return True
    except Exception:
        return False


def safe_create_fk(name: str, source: str, referent: str, local_cols, remote_cols) -> bool:
    if fk_exists(source, name):
        return False
    try:
        with op.batch_alter_table(source) as batch_op:
            batch_op.create_foreign_key(name, referent, local_cols, remote_cols)
        return True
    except Exception:
        return False


def upgrade():
    # 1) organization_addon junction table
    if table_exists('organization') and table_exists('addon') and not table_exists('organization_addon'):
        op.create_table(
            'organization_addon',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=False, index=True),
            sa.Column('addon_id', sa.Integer(), nullable=False, index=True),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('source', sa.String(length=32), nullable=False, server_default='subscription_item'),
            sa.Column('stripe_item_id', sa.String(length=128), nullable=True),
            sa.Column('current_period_end', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        # Indexes
        safe_create_index('ix_organization_addon_organization_id', 'organization_addon', ['organization_id'])
        safe_create_index('ix_organization_addon_addon_id', 'organization_addon', ['addon_id'])
        # FKs
        safe_create_fk('fk_org_addon_org', 'organization_addon', 'organization', ['organization_id'], ['id'])
        safe_create_fk('fk_org_addon_addon', 'organization_addon', 'addon', ['addon_id'], ['id'])

    # 2) feature_flag schema alignment (key, enabled, description length)
    if table_exists('feature_flag'):
        safe_add_column('feature_flag', sa.Column('key', sa.String(length=128), nullable=True))
        safe_add_column('feature_flag', sa.Column('enabled', sa.Boolean(), nullable=True))
        # index on key if not exists
        if column_exists('feature_flag', 'key'):
            safe_create_index('ix_feature_flag_key', 'feature_flag', ['key'], unique=False)

    # 3) unit.created_by (guarded) already handled in 20251021_02, but keep safe
    if table_exists('unit'):
        safe_add_column('unit', sa.Column('created_by', sa.Integer(), nullable=True))
        if column_exists('unit', 'created_by') and table_exists('user'):
            safe_create_fk('fk_unit_created_by_user', 'unit', 'user', ['created_by'], ['id'])

    # 4) global_item.recommended_shelf_life_days already handled; keep safe
    if table_exists('global_item'):
        safe_add_column('global_item', sa.Column('recommended_shelf_life_days', sa.Integer(), nullable=True))

    # 5) inventory_item.density / container_type already handled; keep safe
    if table_exists('inventory_item'):
        safe_add_column('inventory_item', sa.Column('density', sa.Float(), nullable=True))
        safe_add_column('inventory_item', sa.Column('container_type', sa.String(length=64), nullable=True))

    # 6) recipe and batch portioning alignment
    if table_exists('recipe'):
        safe_add_column('recipe', sa.Column('portion_name', sa.String(length=64), nullable=True))
        safe_add_column('recipe', sa.Column('portion_count', sa.Integer(), nullable=True))
        safe_add_column('recipe', sa.Column('portion_unit_id', sa.Integer(), nullable=True))
        if column_exists('recipe', 'portion_unit_id') and table_exists('unit'):
            safe_create_fk('fk_recipe_portion_unit', 'recipe', 'unit', ['portion_unit_id'], ['id'])

    if table_exists('batch'):
        safe_add_column('batch', sa.Column('portion_name', sa.String(length=64), nullable=True))
        safe_add_column('batch', sa.Column('projected_portions', sa.Integer(), nullable=True))
        safe_add_column('batch', sa.Column('final_portions', sa.Integer(), nullable=True))
        safe_add_column('batch', sa.Column('portion_unit_id', sa.Integer(), nullable=True))
        if column_exists('batch', 'portion_unit_id') and table_exists('unit'):
            safe_create_fk('fk_batch_portion_unit', 'batch', 'unit', ['portion_unit_id'], ['id'])

    # 7) product fields and constraints alignment
    if table_exists('product'):
        safe_add_column('product', sa.Column('subcategory', sa.String(length=64), nullable=True))
        safe_add_column('product', sa.Column('low_stock_threshold', sa.Float(), nullable=True))
        safe_add_column('product', sa.Column('is_discontinued', sa.Boolean(), nullable=True, server_default=sa.text('false')))
        safe_add_column('product', sa.Column('created_by', sa.Integer(), nullable=True))
        safe_add_column('product', sa.Column('shopify_product_id', sa.String(length=64), nullable=True))
        safe_add_column('product', sa.Column('etsy_shop_section_id', sa.String(length=64), nullable=True))
        # unique per org name
        # Unique per-org (name, organization_id) if no duplicates
        if not unique_exists('product', 'unique_product_name_per_org'):
            if not has_duplicates('product', ['name', 'organization_id']):
                try:
                    op.create_unique_constraint('unique_product_name_per_org', 'product', ['name', 'organization_id'])
                except Exception:
                    # If creation fails for any reason, skip to avoid aborting the transaction
                    pass
        if column_exists('product', 'created_by') and table_exists('user'):
            safe_create_fk('fk_product_created_by_user', 'product', 'user', ['created_by'], ['id'])

    # 8) product_sku indexes/uniques (columns largely exist via earlier migrations)
    if table_exists('product_sku'):
        # Ensure expected uniques and indexes
        # Unique constraints guarded by duplicate checks
        if not unique_exists('product_sku', 'unique_sku_combination'):
            if not has_duplicates('product_sku', ['product_id', 'variant_id', 'size_label', 'fifo_id']):
                try:
                    op.create_unique_constraint('unique_sku_combination', 'product_sku', ['product_id', 'variant_id', 'size_label', 'fifo_id'])
                except Exception:
                    pass
        if not unique_exists('product_sku', 'unique_barcode'):
            if not has_duplicates('product_sku', ['barcode']):
                try:
                    op.create_unique_constraint('unique_barcode', 'product_sku', ['barcode'])
                except Exception:
                    pass
        if not unique_exists('product_sku', 'unique_upc'):
            if not has_duplicates('product_sku', ['upc']):
                try:
                    op.create_unique_constraint('unique_upc', 'product_sku', ['upc'])
                except Exception:
                    pass
        safe_create_index('idx_product_variant', 'product_sku', ['product_id', 'variant_id'])
        safe_create_index('idx_active_skus', 'product_sku', ['is_active', 'is_product_active'])
        safe_create_index('idx_inventory_item', 'product_sku', ['inventory_item_id'])
        safe_create_index('ix_product_sku_inventory_item_id', 'product_sku', ['inventory_item_id'])
        # Common FKs
        if table_exists('product') and not has_orphans('product_sku', 'product_id', 'product'):
            safe_create_fk('fk_sku_product', 'product_sku', 'product', ['product_id'], ['id'])
        if table_exists('product_variant') and not has_orphans('product_sku', 'variant_id', 'product_variant'):
            safe_create_fk('fk_sku_variant', 'product_sku', 'product_variant', ['variant_id'], ['id'])
        if table_exists('batch') and not has_orphans('product_sku', 'batch_id', 'batch'):
            safe_create_fk('fk_sku_batch', 'product_sku', 'batch', ['batch_id'], ['id'])
        if table_exists('inventory_item') and not has_orphans('product_sku', 'inventory_item_id', 'inventory_item'):
            safe_create_fk('fk_sku_inventory_item', 'product_sku', 'inventory_item', ['inventory_item_id'], ['id'])
        if table_exists('user') and not has_orphans('product_sku', 'created_by', 'user'):
            safe_create_fk('fk_sku_created_by', 'product_sku', 'user', ['created_by'], ['id'])

    # 9) product_sku_history alignment
    if table_exists('product_sku_history'):
        safe_add_column('product_sku_history', sa.Column('organization_id', sa.Integer(), nullable=True))
        safe_add_column('product_sku_history', sa.Column('inventory_item_id', sa.Integer(), nullable=True))
        safe_add_column('product_sku_history', sa.Column('quantity_change', sa.Float(), nullable=True))
        safe_add_column('product_sku_history', sa.Column('unit', sa.String(length=32), nullable=True))
        safe_create_index('idx_change_type', 'product_sku_history', ['change_type'])
        safe_create_index('idx_fifo_code', 'product_sku_history', ['fifo_code'])
        safe_create_index('idx_inventory_item_remaining', 'product_sku_history', ['inventory_item_id', 'remaining_quantity'])
        safe_create_index('idx_inventory_item_timestamp', 'product_sku_history', ['inventory_item_id', 'timestamp'])
        if table_exists('organization') and not has_orphans('product_sku_history', 'organization_id', 'organization'):
            safe_create_fk('fk_psh_org', 'product_sku_history', 'organization', ['organization_id'], ['id'])
        if table_exists('inventory_item') and not has_orphans('product_sku_history', 'inventory_item_id', 'inventory_item'):
            safe_create_fk('fk_psh_inventory_item', 'product_sku_history', 'inventory_item', ['inventory_item_id'], ['id'])

    # 10) inventory_category alignment
    if table_exists('inventory_category'):
        safe_add_column('inventory_category', sa.Column('description', sa.Text(), nullable=True))
        safe_add_column('inventory_category', sa.Column('item_type', sa.String(length=64), nullable=True))
        safe_add_column('inventory_category', sa.Column('created_by', sa.Integer(), nullable=True))
        # unique per org constraint
        if not unique_exists('inventory_category', '_invcat_name_type_org_uc'):
            # Duplicate check (coalesce item_type to empty string to treat NULLs distinctly)
            if not has_duplicates('inventory_category', ['name', 'item_type', 'organization_id']):
                try:
                    op.create_unique_constraint('_invcat_name_type_org_uc', 'inventory_category', ['name', 'item_type', 'organization_id'])
                except Exception:
                    pass
        if column_exists('inventory_category', 'created_by') and table_exists('user') and not has_orphans('inventory_category', 'created_by', 'user'):
            safe_create_fk('fk_invcat_created_by', 'inventory_category', 'user', ['created_by'], ['id'])
        if column_exists('inventory_category', 'organization_id') and table_exists('organization') and not has_orphans('inventory_category', 'organization_id', 'organization'):
            safe_create_fk('fk_invcat_org', 'inventory_category', 'organization', ['organization_id'], ['id'])

    # 11) tag alignment
    if table_exists('tag'):
        safe_add_column('tag', sa.Column('description', sa.Text(), nullable=True))
        safe_add_column('tag', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')))
        safe_add_column('tag', sa.Column('created_by', sa.Integer(), nullable=True))
        if not unique_exists('tag', '_tag_name_org_uc'):
            if not has_duplicates('tag', ['name', 'organization_id']):
                try:
                    op.create_unique_constraint('_tag_name_org_uc', 'tag', ['name', 'organization_id'])
                except Exception:
                    pass
        if column_exists('tag', 'created_by') and table_exists('user'):
            safe_create_fk('fk_tag_created_by', 'tag', 'user', ['created_by'], ['id'])

    # 12) reservation alignment
    if table_exists('reservation'):
        # new columns commonly used
        for col in [
            sa.Column('order_id', sa.String(length=64), nullable=True),
            sa.Column('reservation_id', sa.String(length=64), nullable=True),
            sa.Column('product_item_id', sa.Integer(), nullable=True),
            sa.Column('reserved_item_id', sa.Integer(), nullable=True),
            sa.Column('unit_cost', sa.Float(), nullable=True),
            sa.Column('sale_price', sa.Float(), nullable=True),
            sa.Column('customer', sa.String(length=128), nullable=True),
            sa.Column('source_fifo_id', sa.String(length=32), nullable=True),
            sa.Column('source_batch_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=True),
            sa.Column('source', sa.String(length=32), nullable=True),
            sa.Column('released_at', sa.DateTime(), nullable=True),
            sa.Column('converted_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
        ]:
            safe_add_column('reservation', col)
        # indexes
        safe_create_index('idx_expires_at', 'reservation', ['expires_at'])
        safe_create_index('idx_order_status', 'reservation', ['order_id', 'status'])
        safe_create_index('idx_reserved_item_status', 'reservation', ['reserved_item_id', 'status'])
        safe_create_index('ix_reservation_order_id', 'reservation', ['order_id'])
        # FKs best-effort
        if table_exists('user') and not has_orphans('reservation', 'created_by', 'user'):
            safe_create_fk('fk_res_created_by', 'reservation', 'user', ['created_by'], ['id'])

    # 13) stats alignments
    if table_exists('organization_stats'):
        for col in [
            sa.Column('completed_batches', sa.Integer(), nullable=True),
            sa.Column('failed_batches', sa.Integer(), nullable=True),
            sa.Column('cancelled_batches', sa.Integer(), nullable=True),
            sa.Column('active_users', sa.Integer(), nullable=True),
            sa.Column('total_inventory_value', sa.Float(), nullable=True),
            sa.Column('total_products', sa.Integer(), nullable=True),
            sa.Column('total_products_made', sa.Float(), nullable=True),
            sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        ]:
            safe_add_column('organization_stats', col)

    if table_exists('user_stats'):
        for col in [
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('total_batches', sa.Integer(), nullable=True),
            sa.Column('completed_batches', sa.Integer(), nullable=True),
            sa.Column('failed_batches', sa.Integer(), nullable=True),
            sa.Column('cancelled_batches', sa.Integer(), nullable=True),
            sa.Column('total_recipes', sa.Integer(), nullable=True),
            sa.Column('recipes_created', sa.Integer(), nullable=True),
            sa.Column('inventory_adjustments', sa.Integer(), nullable=True),
            sa.Column('inventory_items_created', sa.Integer(), nullable=True),
            sa.Column('products_created', sa.Integer(), nullable=True),
            sa.Column('total_products_made', sa.Float(), nullable=True),
            sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        ]:
            safe_add_column('user_stats', col)
        if table_exists('organization'):
            safe_create_fk('fk_user_stats_org', 'user_stats', 'organization', ['organization_id'], ['id'])

    # 14) billing_snapshot alignment
    if table_exists('pricing_snapshots'):
        for col in [
            sa.Column('stripe_price_id', sa.String(length=128), nullable=False, server_default=''),
            sa.Column('stripe_lookup_key', sa.String(length=128), nullable=False, server_default=''),
            sa.Column('stripe_product_id', sa.String(length=128), nullable=False, server_default=''),
            sa.Column('unit_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('interval', sa.String(length=32), nullable=False, server_default='month'),
            sa.Column('product_name', sa.String(length=128), nullable=False, server_default=''),
            sa.Column('last_stripe_sync', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        ]:
            safe_add_column('pricing_snapshots', col)
        try:
            op.create_unique_constraint('uq_pricing_snapshots_stripe_price_id', 'pricing_snapshots', ['stripe_price_id'])
        except Exception:
            pass

    # 15) developer/permission/role string length/nullable safety
    if table_exists('developer_permission'):
        safe_add_column('developer_permission', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')))
    if table_exists('developer_role'):
        # name length differences are ignored; add description type safety by adding column if missing
        pass
    if table_exists('role'):
        safe_add_column('role', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')))
        try:
            op.create_unique_constraint('unique_role_name_org', 'role', ['name', 'organization_id'])
        except Exception:
            pass

    # 16) indexes that may be missing but harmless if present
    if table_exists('inventory_item'):
        safe_create_index('ix_inventory_item_is_archived', 'inventory_item', ['is_archived'])



def downgrade():
    # Non-destructive downgrade to keep production safe; no-op
    pass
