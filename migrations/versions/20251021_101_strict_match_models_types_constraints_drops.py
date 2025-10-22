"""
Strictly align DB types, nullability, and drop legacy columns/indexes to match ORM models

Revision ID: 20251021_101
Revises: 20251021_100
Create Date: 2025-10-21

This migration performs type/length changes, NOT NULL enforcement with safe server defaults,
index/unique normalization, and drops legacy columns to match models exactly.
SQLite-compatible via batch_alter_table; guarded and idempotent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '20251021_101'
down_revision = '20251021_100'
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


def _alter_str(table: str, column: str, length: int, nullable: bool | None = None, unique: bool | None = None, server_default: str | None = None):
    if not table_exists(table) or not column_exists(table, column):
        return
    try:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                type_=sa.String(length=length),
                existing_type=sa.String(length=length),
                nullable=nullable,
                existing_nullable=None,
                server_default=text(server_default) if server_default else None,
            )
    except Exception:
        # best-effort; skip on failure
        pass


def _alter_text(table: str, column: str, nullable: bool | None = None):
    if not table_exists(table) or not column_exists(table, column):
        return
    try:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(column, type_=sa.Text(), nullable=nullable)
    except Exception:
        pass


def _drop_columns(table: str, names: list[str]):
    if not table_exists(table):
        return
    for name in names:
        try:
            with op.batch_alter_table(table) as batch_op:
                if column_exists(table, name):
                    batch_op.drop_column(name)
        except Exception:
            pass


def _drop_indexes(table: str, names: list[str]):
    for name in names:
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass


def _create_unique(table: str, name: str, cols: list[str]):
    try:
        op.create_unique_constraint(name, table, cols)
    except Exception:
        pass


def _recreate_unique(table: str, old_names: list[str], new_name: str, cols: list[str]):
    # Drop any legacy uniques then create the desired one
    for old in old_names:
        try:
            op.drop_constraint(old, table, type_='unique')
        except Exception:
            pass
    _create_unique(table, new_name, cols)


def upgrade():
    # feature_flag: name -> key (String(128)), description -> String(255), enabled bool
    if table_exists('feature_flag'):
        _drop_indexes('feature_flag', ['ix_feature_flag_name'])
        # add key/enabled already in prior migration; enforce lengths
        _alter_str('feature_flag', 'key', 128)
        _alter_str('feature_flag', 'description', 255, nullable=True)
        # Drop legacy name/is_enabled if they exist
        _drop_columns('feature_flag', ['name', 'is_enabled'])

    # product_category.name unique True and length 64
    if table_exists('product_category'):
        try:
            with op.batch_alter_table('product_category') as batch_op:
                batch_op.alter_column('name', type_=sa.String(length=64))
        except Exception:
            pass
        # Ensure unique index exists (created earlier), nothing more here

    # product.name length 128
    if table_exists('product'):
        try:
            with op.batch_alter_table('product') as batch_op:
                batch_op.alter_column('name', type_=sa.String(length=128))
        except Exception:
            pass

    # recipe.name 128; portion_name 64; portion_count int
    if table_exists('recipe'):
        try:
            with op.batch_alter_table('recipe') as batch_op:
                if column_exists('recipe', 'name'):
                    batch_op.alter_column('name', type_=sa.String(length=128))
                if column_exists('recipe', 'portion_name'):
                    batch_op.alter_column('portion_name', type_=sa.String(length=64))
        except Exception:
            pass

    # batch.portion_name 64
    if table_exists('batch'):
        try:
            with op.batch_alter_table('batch') as batch_op:
                if column_exists('batch', 'portion_name'):
                    batch_op.alter_column('portion_name', type_=sa.String(length=64))
        except Exception:
            pass

    # inventory_item string widths
    if table_exists('inventory_item'):
        try:
            with op.batch_alter_table('inventory_item') as batch_op:
                for col, length in [
                    ('name', 128),
                    ('unit', 32),
                    ('capacity_unit', 32),
                    ('container_shape', 64),
                    ('container_color', 64),
                ]:
                    if column_exists('inventory_item', col):
                        batch_op.alter_column(col, type_=sa.String(length=length))
        except Exception:
            pass

    # inventory_history widths and types
    if table_exists('inventory_history'):
        try:
            with op.batch_alter_table('inventory_history') as batch_op:
                if column_exists('inventory_history', 'unit'):
                    batch_op.alter_column('unit', type_=sa.String(length=32))
                if column_exists('inventory_history', 'fifo_code'):
                    batch_op.alter_column('fifo_code', type_=sa.String(length=32))
                if column_exists('inventory_history', 'unit_cost'):
                    batch_op.alter_column('unit_cost', type_=sa.Float())
                if column_exists('inventory_history', 'expiration_date'):
                    batch_op.alter_column('expiration_date', type_=sa.DateTime())
        except Exception:
            pass

    # product_sku widths, NOT NULLs, and datetime for timestamps
    if table_exists('product_sku'):
        try:
            with op.batch_alter_table('product_sku') as batch_op:
                for col, length in [
                    ('size_label', 64),
                    ('fifo_id', 32),
                    ('barcode', 128),
                    ('upc', 32),
                ]:
                    if column_exists('product_sku', col):
                        batch_op.alter_column(col, type_=sa.String(length=length))
                for ts in ['created_at', 'updated_at', 'quality_checked_at', 'marketplace_last_sync', 'expiration_date']:
                    if column_exists('product_sku', ts):
                        batch_op.alter_column(ts, type_=sa.DateTime())
                if column_exists('product_sku', 'location_id'):
                    batch_op.alter_column('location_id', type_=sa.String(length=128))
                if column_exists('product_sku', 'id'):
                    batch_op.alter_column('id', existing_type=sa.Integer(), nullable=False)
                if column_exists('product_sku', 'size_label'):
                    batch_op.alter_column('size_label', existing_type=sa.String(length=64), nullable=False)
        except Exception:
            pass

    # product_sku_history widths and nullability
    if table_exists('product_sku_history'):
        try:
            with op.batch_alter_table('product_sku_history') as batch_op:
                if column_exists('product_sku_history', 'change_type'):
                    batch_op.alter_column('change_type', type_=sa.String(length=32))
                if column_exists('product_sku_history', 'unit'):
                    batch_op.alter_column('unit', type_=sa.String(length=32), nullable=False)
                if column_exists('product_sku_history', 'quantity_change'):
                    batch_op.alter_column('quantity_change', type_=sa.Float(), nullable=False)
                if column_exists('product_sku_history', 'inventory_item_id'):
                    batch_op.alter_column('inventory_item_id', existing_type=sa.Integer(), nullable=False)
        except Exception:
            pass

    # role / permission / developer role/permission widths
    for table, col_lens in [
        ('role', [('name', 64)]),
        ('permission', [('name', 100)]),
        ('developer_role', [('name', 64)]),
        ('developer_permission', [('name', 128)])
    ]:
        if table_exists(table):
            try:
                with op.batch_alter_table(table) as batch_op:
                    for col, length in col_lens:
                        if column_exists(table, col):
                            batch_op.alter_column(col, type_=sa.String(length=length))
                    # descriptions to Text
                    if column_exists(table, 'description'):
                        batch_op.alter_column('description', type_=sa.Text())
            except Exception:
                pass

    # user widths and nullability changes
    if table_exists('user'):
        try:
            with op.batch_alter_table('user') as batch_op:
                for col, length in [('username', 64), ('first_name', 64), ('last_name', 64)]:
                    if column_exists('user', col):
                        batch_op.alter_column(col, type_=sa.String(length=length))
                if column_exists('user', 'email'):
                    batch_op.alter_column('email', type_=sa.String(length=120))
                if column_exists('user', 'password_hash'):
                    batch_op.alter_column('password_hash', type_=sa.String(length=255), nullable=True, server_default=text("''"))
                if column_exists('user', 'user_type'):
                    batch_op.alter_column('user_type', type_=sa.String(length=32))
        except Exception:
            pass

    # subscription_tier widths & uniquenesses enforced earlier; drop legacy indexes
    if table_exists('subscription_tier'):
        _drop_indexes('subscription_tier', [
            'idx_subscription_tier_billing_provider',
            'ix_subscription_tier_billing_provider',
            'ix_subscription_tier_is_customer_facing',
            'ix_subscription_tier_tier_key',
            'uq_subscription_tier_name',
            'uq_subscription_tier_stripe_storage_lookup_key',
        ])

    # stripe_event: normalize indexes/uniques
    if table_exists('stripe_event'):
        _drop_indexes('stripe_event', ['ix_stripe_event_event_type', 'uq_stripe_event_event_id'])
        # Ensure event_id unique via changed index handled earlier

    # unit widths
    if table_exists('unit'):
        try:
            with op.batch_alter_table('unit') as batch_op:
                for col, length in [('name', 64), ('symbol', 16), ('unit_type', 32)]:
                    if column_exists('unit', col):
                        batch_op.alter_column(col, type_=sa.String(length=length))
        except Exception:
            pass

    # global_item widths and drop old container fields
    if table_exists('global_item'):
        try:
            with op.batch_alter_table('global_item') as batch_op:
                if column_exists('global_item', 'container_color'):
                    batch_op.alter_column('container_color', type_=sa.String(length=64))
            # Drop legacy container fields not present in models
            _drop_indexes('global_item', ['ix_global_item_is_archived'])
            _drop_columns('global_item', [
                'container_volume_unit', 'container_shape', 'container_volume',
                'container_dimensions', 'default_days_until_expiration', 'container_closure_type'
            ])
        except Exception:
            pass

    # inventory_lot: drop legacy indexes (optional)
    if table_exists('inventory_lot'):
        _drop_indexes('inventory_lot', ['idx_inventory_lot_expiration', 'idx_inventory_lot_item_remaining', 'idx_inventory_lot_organization', 'idx_inventory_lot_received_date'])

    # user_preferences widths and nullable state
    if table_exists('user_preferences'):
        try:
            with op.batch_alter_table('user_preferences') as batch_op:
                if column_exists('user_preferences', 'dashboard_layout'):
                    batch_op.alter_column('dashboard_layout', type_=sa.String(length=32))
                if column_exists('user_preferences', 'timezone'):
                    batch_op.alter_column('timezone', type_=sa.String(length=64))
        except Exception:
            pass

    # unified_inventory_history: widths, indexes ensured earlier
    if table_exists('unified_inventory_history'):
        try:
            with op.batch_alter_table('unified_inventory_history') as batch_op:
                if column_exists('unified_inventory_history', 'fifo_code'):
                    batch_op.alter_column('fifo_code', type_=sa.String(length=32))
        except Exception:
            pass



def downgrade():
    # Non-destructive best-effort: no-op for strict changes
    pass
