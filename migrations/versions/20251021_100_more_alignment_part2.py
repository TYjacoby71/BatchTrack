"""
Further align DB schema with ORM models (part 2)

Revision ID: 20251021_100
Revises: 20251021_99
Create Date: 2025-10-21

Safe, idempotent migration that adds missing columns, FKs, and constraints
not covered by prior alignment. Designed to work with SQLite and Postgres.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from contextlib import contextmanager

# Use a SAVEPOINT so failed DDL doesn't abort the outer transaction
@contextmanager
def in_savepoint():
    conn = op.get_bind()
    nested = conn.begin_nested()
    try:
        yield
        nested.commit()
    except Exception:
        try:
            nested.rollback()
        except Exception:
            pass

revision = '20251021_100'
down_revision = '20251021_99'
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


def unique_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        for cons in insp.get_unique_constraints(table):
            if cons.get('name') == name:
                return True
    except Exception:
        return False
    return False


def get_fk_name_for_columns(table: str, local_cols: list[str]) -> str | None:
    if not table_exists(table):
        return None
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        for fk in insp.get_foreign_keys(table):
            if fk.get('constrained_columns') == local_cols:
                return fk.get('name')
    except Exception:
        return None
    return None


def fk_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        insp = inspect(bind)
        return any(fk.get('name') == name for fk in insp.get_foreign_keys(table))
    except Exception:
        return False


def has_duplicates(table: str, columns: list[str]) -> bool:
    """Return True if duplicate rows exist for the given columns (ignores rows with NULLs)."""
    if not table_exists(table):
        return False
    bind = op.get_bind()
    cols_csv = ", ".join(columns)
    not_null_cond = " AND ".join([f"{c} IS NOT NULL" for c in columns]) or "TRUE"
    q = text(
        f"""
        SELECT 1 FROM {table}
        WHERE {not_null_cond}
        GROUP BY {cols_csv}
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )
    # Execute in a SAVEPOINT to avoid aborting outer transaction on error
    ran = False
    found = False
    with in_savepoint():
        res = bind.execute(q).first()
        found = res is not None
        ran = True
    if not ran:
        # Assume duplicates (skip creating constraint) if check failed
        return True
    return found


def has_orphans(source: str, local_col: str, referent: str, remote_col: str = 'id') -> bool:
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
    ran = False
    exists = False
    with in_savepoint():
        res = bind.execute(q).first()
        exists = res is not None
        ran = True
    if not ran:
        # On error, assume unsafe (orphans present)
        return True
    return exists


def safe_add_column(table: str, col: sa.Column) -> bool:
    if not table_exists(table):
        return False
    if column_exists(table, col.name):
        return False
    with in_savepoint():
        try:
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(col)
            return True
        except Exception:
            return False


def safe_drop_column(table: str, column: str) -> bool:
    if not table_exists(table) or not column_exists(table, column):
        return False
    with in_savepoint():
        try:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column(column)
            return True
        except Exception:
            return False


def safe_create_index(name: str, table: str, columns: list[str], unique: bool = False) -> bool:
    if index_exists(table, name):
        return False
    with in_savepoint():
        try:
            op.create_index(name, table, columns, unique=unique)
            return True
        except Exception:
            return False


def safe_drop_index(name: str, table: str) -> bool:
    if not index_exists(table, name):
        return False
    with in_savepoint():
        try:
            op.drop_index(name, table_name=table)
            return True
        except Exception:
            return False


def safe_create_unique(name: str, table: str, columns: list[str]) -> bool:
    if unique_exists(table, name) or index_exists(table, name):
        return False
    # Avoid creating if duplicates exist; would abort transaction
    if has_duplicates(table, columns):
        return False
    with in_savepoint():
        try:
            op.create_unique_constraint(name, table, columns)
            return True
        except Exception:
            return False


def safe_drop_unique(name: str, table: str) -> bool:
    if not unique_exists(table, name):
        return False
    with in_savepoint():
        try:
            op.drop_constraint(name, table, type_='unique')
            return True
        except Exception:
            return False


def safe_create_fk(name: str, source: str, referent: str, local_cols, remote_cols) -> bool:
    if fk_exists(source, name):
        return False
    # Only attempt if there are no orphaned values
    if len(local_cols) == 1 and not isinstance(local_cols, (list, tuple)):
        cols = [local_cols]
    else:
        cols = list(local_cols)
    # Only handle single-column FK or simple first column check
    local_col = cols[0] if cols else None
    if local_col and has_orphans(source, local_col, referent, remote_cols[0] if remote_cols else 'id'):
        return False
    with in_savepoint():
        try:
            with op.batch_alter_table(source) as batch_op:
                batch_op.create_foreign_key(name, referent, local_cols, remote_cols)
            return True
        except Exception:
            return False


def safe_drop_fk_by_name(table: str, name: str) -> bool:
    if not fk_exists(table, name):
        return False
    with in_savepoint():
        try:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(name, type_='foreignkey')
            return True
        except Exception:
            return False


def safe_drop_fk_by_columns(table: str, local_cols: list[str]) -> bool:
    name = get_fk_name_for_columns(table, local_cols)
    if not name:
        return False
    return safe_drop_fk_by_name(table, name)


def safe_alter_not_null(table: str, column: str, nullable: bool, server_default: str | None = None):
    if not table_exists(table) or not column_exists(table, column):
        return False
    # Pre-check data to avoid aborting the transaction on NOT NULL
    if not nullable:
        try:
            bind = op.get_bind()
            res = bind.execute(text(f"SELECT 1 FROM {table} WHERE {column} IS NULL LIMIT 1"))
            if res.first() is not None:
                return False
        except Exception:
            # If check fails, err on safe side and skip
            return False
    with in_savepoint():
        try:
            with op.batch_alter_table(table) as batch_op:
                batch_op.alter_column(column, existing_type=sa.Text(), nullable=nullable, server_default=server_default)
            return True
        except Exception:
            # Fallback: try without existing_type
            try:
                with op.batch_alter_table(table) as batch_op:
                    batch_op.alter_column(column, nullable=nullable, server_default=server_default)
                return True
            except Exception:
                return False


def upgrade():
    # === Batch-related tables ===
    if table_exists('batch_consumable'):
        safe_add_column('batch_consumable', sa.Column('quantity_used', sa.Float(), nullable=True))
        safe_add_column('batch_consumable', sa.Column('cost_per_unit', sa.Float(), nullable=True))
        safe_add_column('batch_consumable', sa.Column('total_cost', sa.Float(), nullable=True))
        safe_add_column('batch_consumable', sa.Column('organization_id', sa.Integer(), nullable=True))
        if column_exists('batch_consumable', 'organization_id') and table_exists('organization'):
            safe_create_fk('fk_batch_consumable_org', 'batch_consumable', 'organization', ['organization_id'], ['id'])
        # Drop legacy columns if present
        for legacy in ['notes', 'order_position', 'quantity']:
            safe_drop_column('batch_consumable', legacy)

    if table_exists('batch_ingredient'):
        safe_add_column('batch_ingredient', sa.Column('organization_id', sa.Integer(), nullable=True))
        if column_exists('batch_ingredient', 'organization_id') and table_exists('organization'):
            safe_create_fk('fk_batch_ingredient_org', 'batch_ingredient', 'organization', ['organization_id'], ['id'])
        safe_drop_column('batch_ingredient', 'fifo_deduction_log')

    if table_exists('batch_inventory_log'):
        for col in [
            sa.Column('action', sa.String(length=32), nullable=True),
            sa.Column('quantity_change', sa.Float(), nullable=True),
            sa.Column('old_stock', sa.Float(), nullable=True),
            sa.Column('new_stock', sa.Float(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
        ]:
            safe_add_column('batch_inventory_log', col)
        if column_exists('batch_inventory_log', 'organization_id') and table_exists('organization'):
            safe_create_fk('fk_batch_inventory_log_org', 'batch_inventory_log', 'organization', ['organization_id'], ['id'])
        # Drop legacy columns
        for legacy in ['cost_per_unit', 'quantity_after', 'user_id', 'total_cost', 'quantity_before', 'quantity_used']:
            safe_drop_column('batch_inventory_log', legacy)
        # Attempt to drop FK on user_id if it existed
        safe_drop_fk_by_columns('batch_inventory_log', ['user_id'])

    if table_exists('batch_timer'):
        for col in [
            sa.Column('name', sa.String(length=128), nullable=True),
            sa.Column('duration_seconds', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
        ]:
            safe_add_column('batch_timer', col)
        if column_exists('batch_timer', 'organization_id') and table_exists('organization'):
            safe_create_fk('fk_batch_timer_org', 'batch_timer', 'organization', ['organization_id'], ['id'])
        if column_exists('batch_timer', 'created_by') and table_exists('user'):
            safe_create_fk('fk_batch_timer_created_by', 'batch_timer', 'user', ['created_by'], ['id'])
        # Drop legacy columns
        for legacy in ['duration_minutes', 'notes', 'is_active', 'timer_name']:
            safe_drop_column('batch_timer', legacy)

    # === Billing snapshots ===
    if table_exists('billing_snapshots'):
        if not fk_exists('billing_snapshots', 'fk_billing_snapshots_org') and table_exists('organization'):
            safe_create_fk('fk_billing_snapshots_org', 'billing_snapshots', 'organization', ['organization_id'], ['id'])
        # Tighten NOT NULL where safe via server defaults
        for col, default in [
            ('organization_id', None),
            ('confirmed_tier', "''"),
            ('confirmed_status', "''"),
            ('period_start', "CURRENT_TIMESTAMP"),
            ('period_end', "CURRENT_TIMESTAMP"),
            ('last_stripe_sync', "CURRENT_TIMESTAMP"),
        ]:
            safe_alter_not_null('billing_snapshots', col, nullable=False, server_default=text(default) if default else None)
        # Optionally drop updated_at if present (deprecated)
        safe_drop_column('billing_snapshots', 'updated_at')

    # === Conversion log ===
    if table_exists('conversion_log'):
        for col in [
            sa.Column('amount', sa.Float(), nullable=True),
            sa.Column('result', sa.Float(), nullable=True),
            sa.Column('conversion_type', sa.String(length=64), nullable=True),
            sa.Column('ingredient_name', sa.String(length=128), nullable=True),
        ]:
            safe_add_column('conversion_log', col)
        # Ensure user_id not null if possible
        safe_alter_not_null('conversion_log', 'user_id', nullable=False)
        # Drop legacy fields
        for legacy in ['conversion_factor', 'category_density', 'to_amount', 'from_amount']:
            safe_drop_column('conversion_log', legacy)

    # === Custom unit mapping ===
    if table_exists('custom_unit_mapping'):
        safe_add_column('custom_unit_mapping', sa.Column('created_by', sa.Integer(), nullable=True))
        if column_exists('custom_unit_mapping', 'created_by') and table_exists('user'):
            safe_create_fk('fk_custom_unit_mapping_created_by', 'custom_unit_mapping', 'user', ['created_by'], ['id'])
        # Drop legacy ingredient_id + FK
        safe_drop_fk_by_columns('custom_unit_mapping', ['ingredient_id'])
        safe_drop_column('custom_unit_mapping', 'ingredient_id')

    # === Freshness snapshot ===
    if table_exists('freshness_snapshot'):
        # Drop legacy indexes if present
        for idx in ['ix_freshness_snapshot_date', 'ix_freshness_snapshot_item', 'ix_freshness_snapshot_org']:
            safe_drop_index(idx, 'freshness_snapshot')
        # Unique constraint on date/org/item
        safe_create_unique('uq_freshness_snapshot_unique', 'freshness_snapshot', ['snapshot_date', 'organization_id', 'inventory_item_id'])

    # === Inventory item additions and constraints ===
    if table_exists('inventory_item'):
        for col in [
            sa.Column('type', sa.String(length=32), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
            sa.Column('is_archived', sa.Boolean(), nullable=True, server_default=sa.text('false')),
            sa.Column('is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
            sa.Column('shelf_life_days', sa.Integer(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('density_source', sa.String(length=32), nullable=True),
            sa.Column('intermediate', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        ]:
            safe_add_column('inventory_item', col)
        # Per-org unique on (organization_id, name)
        safe_create_unique('_org_name_uc', 'inventory_item', ['organization_id', 'name'])
        # Indexes
        safe_create_index('ix_inventory_item_type', 'inventory_item', ['type'])
        safe_create_index('ix_inventory_item_is_archived', 'inventory_item', ['is_archived'])
        safe_create_index('ix_inventory_item_org', 'inventory_item', ['organization_id'])
        # FKs
        if table_exists('inventory_category'):
            safe_create_fk('fk_inventory_item_invcat', 'inventory_item', 'inventory_category', ['inventory_category_id'], ['id'])
        if table_exists('global_item'):
            safe_create_fk('fk_inventory_item_global', 'inventory_item', 'global_item', ['global_item_id'], ['id'])
        if table_exists('user'):
            safe_create_fk('fk_inventory_item_created_by', 'inventory_item', 'user', ['created_by'], ['id'])
        # Drop legacy columns (best-effort, safe)
        for legacy in [
            'item_type', 'purchase_date', 'fifo_code', 'storage_location', 'batch_code',
            'container_volume', 'updated_at', 'notes', 'reference_guide_url', 'supplier',
            'container_dimensions', 'reference_item_type', 'container_closure_type'
        ]:
            safe_drop_column('inventory_item', legacy)

    # === Product variant ===
    if table_exists('product_variant'):
        for col in [
            sa.Column('color', sa.String(length=32), nullable=True),
            sa.Column('material', sa.String(length=64), nullable=True),
            sa.Column('scent', sa.String(length=64), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
        ]:
            safe_add_column('product_variant', col)
        if table_exists('user'):
            safe_create_fk('fk_product_variant_created_by', 'product_variant', 'user', ['created_by'], ['id'])
        if table_exists('organization'):
            safe_create_fk('fk_product_variant_org', 'product_variant', 'organization', ['organization_id'], ['id'])
        safe_create_unique('unique_product_variant', 'product_variant', ['product_id', 'name'])
        # Drop legacy columns
        for legacy in ['recipe_id', 'cost_modifier', 'price_modifier', 'updated_at']:
            safe_drop_column('product_variant', legacy)

    # === Recipe additions and cleanup ===
    if table_exists('recipe'):
        for col in [
            sa.Column('label_prefix', sa.String(length=8), nullable=True),
            sa.Column('qr_image', sa.String(length=128), nullable=True),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('is_locked', sa.Boolean(), nullable=True, server_default=sa.text('false')),
            sa.Column('predicted_yield', sa.Float(), nullable=True, server_default='0'),
            sa.Column('predicted_yield_unit', sa.String(length=50), nullable=True, server_default='oz'),
            sa.Column('allowed_containers', sa.PickleType(), nullable=True),
        ]:
            safe_add_column('recipe', col)
        if column_exists('recipe', 'parent_id'):
            safe_create_fk('fk_recipe_parent', 'recipe', 'recipe', ['parent_id'], ['id'])
        # Drop legacy columns
        for legacy in ['yield_unit', 'description', 'base_yield', 'tags', 'notes', 'version', 'is_active']:
            safe_drop_column('recipe', legacy)

    # === Recipe ingredients/consumables ===
    if table_exists('recipe_ingredient'):
        safe_add_column('recipe_ingredient', sa.Column('order_position', sa.Integer(), nullable=True))
        safe_add_column('recipe_ingredient', sa.Column('organization_id', sa.Integer(), nullable=True))
        if table_exists('organization'):
            safe_create_fk('fk_recipe_ingredient_org', 'recipe_ingredient', 'organization', ['organization_id'], ['id'])
        for legacy in ['order_index', 'created_at', 'updated_at']:
            safe_drop_column('recipe_ingredient', legacy)

    if table_exists('recipe_consumable'):
        safe_add_column('recipe_consumable', sa.Column('organization_id', sa.Integer(), nullable=True))
        if table_exists('organization'):
            safe_create_fk('fk_recipe_consumable_org', 'recipe_consumable', 'organization', ['organization_id'], ['id'])

    # === Inventory history ===
    if table_exists('inventory_history'):
        for col in [
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('used_for_batch_id', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('quantity_used', sa.Float(), nullable=True),
        ]:
            safe_add_column('inventory_history', col)
        if table_exists('batch'):
            safe_create_fk('fk_inventory_history_used_for_batch', 'inventory_history', 'batch', ['used_for_batch_id'], ['id'])
        if table_exists('organization'):
            safe_create_fk('fk_inventory_history_org', 'inventory_history', 'organization', ['organization_id'], ['id'])
        # Drop legacy indexes if exist
        for idx in ['idx_inventory_history_fifo_code', 'idx_inventory_history_item_remaining', 'idx_inventory_history_timestamp']:
            safe_drop_index(idx, 'inventory_history')

    # === Product category unique by name ===
    if table_exists('product_category'):
        # Try to create a unique index/constraint on name
        safe_create_index('ix_product_category_name', 'product_category', ['name'], unique=True)
        # Drop legacy description column
        safe_drop_column('product_category', 'description')



def downgrade():
    # Best-effort reversal: drop added constraints/columns

    # Product category
    if table_exists('product_category'):
        # Drop unique index if we created it
        try:
            op.drop_index('ix_product_category_name', table_name='product_category')
        except Exception:
            pass
        # Cannot reliably restore description once dropped; skip
        pass

    # Inventory history
    for col in ['quantity_used', 'organization_id', 'used_for_batch_id', 'note']:
        safe_drop_column('inventory_history', col)

    # Recipe consumable/ingredient
    if table_exists('recipe_consumable'):
        safe_drop_fk_by_name('recipe_consumable', 'fk_recipe_consumable_org')
        safe_drop_column('recipe_consumable', 'organization_id')
    if table_exists('recipe_ingredient'):
        safe_drop_fk_by_name('recipe_ingredient', 'fk_recipe_ingredient_org')
        for col in ['organization_id', 'order_position']:
            safe_drop_column('recipe_ingredient', col)

    # Recipe
    if table_exists('recipe'):
        safe_drop_fk_by_name('recipe', 'fk_recipe_parent')
        for col in ['allowed_containers', 'predicted_yield_unit', 'predicted_yield', 'is_locked', 'parent_id', 'qr_image', 'label_prefix']:
            safe_drop_column('recipe', col)

    # Product variant
    if table_exists('product_variant'):
        safe_drop_fk_by_name('product_variant', 'fk_product_variant_org')
        safe_drop_fk_by_name('product_variant', 'fk_product_variant_created_by')
        safe_drop_unique('unique_product_variant', 'product_variant')
        for col in ['organization_id', 'created_by', 'scent', 'material', 'color']:
            safe_drop_column('product_variant', col)

    # Inventory item
    if table_exists('inventory_item'):
        for idx in ['ix_inventory_item_org', 'ix_inventory_item_is_archived', 'ix_inventory_item_type']:
            safe_drop_index(idx, 'inventory_item')
        safe_drop_unique('_org_name_uc', 'inventory_item')
        for col in ['intermediate', 'density_source', 'created_by', 'shelf_life_days', 'is_perishable', 'is_archived', 'is_active', 'type']:
            safe_drop_column('inventory_item', col)

    # Freshness snapshot
    if table_exists('freshness_snapshot'):
        safe_drop_unique('uq_freshness_snapshot_unique', 'freshness_snapshot')
        # Not re-creating old indexes for simplicity

    # Custom unit mapping
    if table_exists('custom_unit_mapping'):
        safe_drop_fk_by_name('custom_unit_mapping', 'fk_custom_unit_mapping_created_by')
        safe_drop_column('custom_unit_mapping', 'created_by')
        # Not restoring ingredient_id

    # Conversion log
    if table_exists('conversion_log'):
        for col in ['ingredient_name', 'conversion_type', 'result', 'amount']:
            safe_drop_column('conversion_log', col)

    # Billing snapshots
    if table_exists('billing_snapshots'):
        safe_drop_fk_by_name('billing_snapshots', 'fk_billing_snapshots_org')
        # Not changing nullability back for safety

    # Batch timer
    if table_exists('batch_timer'):
        safe_drop_fk_by_name('batch_timer', 'fk_batch_timer_created_by')
        safe_drop_fk_by_name('batch_timer', 'fk_batch_timer_org')
        for col in ['created_by', 'organization_id', 'status', 'duration_seconds', 'name']:
            safe_drop_column('batch_timer', col)

    # Batch inventory log
    if table_exists('batch_inventory_log'):
        safe_drop_fk_by_name('batch_inventory_log', 'fk_batch_inventory_log_org')
        for col in ['organization_id', 'new_stock', 'old_stock', 'quantity_change', 'action']:
            safe_drop_column('batch_inventory_log', col)

    # Batch ingredient
    if table_exists('batch_ingredient'):
        safe_drop_fk_by_name('batch_ingredient', 'fk_batch_ingredient_org')
        safe_drop_column('batch_ingredient', 'organization_id')

    # Batch consumable
    if table_exists('batch_consumable'):
        safe_drop_fk_by_name('batch_consumable', 'fk_batch_consumable_org')
        for col in ['organization_id', 'total_cost', 'cost_per_unit', 'quantity_used']:
            safe_drop_column('batch_consumable', col)
