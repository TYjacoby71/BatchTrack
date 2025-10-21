"""
Add global_item_alias table and performance indexes

Revision ID: 20250930_1
Revises: 20250925_04
Create Date: 2025-09-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import table_exists, index_exists, safe_create_index, is_postgresql


revision = '20250930_1'
down_revision = '20250925_04'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    
    print("=== Adding alias table and performance indexes ===")
    
    # 1) Alias table for GlobalItem aka names
    if not table_exists('global_item_alias'):
        print("   Creating global_item_alias table...")
        op.create_table(
            'global_item_alias',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('alias', sa.Text(), nullable=False, index=True),
        )
        print("   ✅ global_item_alias table created")
    else:
        print("   ✅ global_item_alias table already exists - skipping")

    # 2) GIN/tsvector index for fast alias search (PostgreSQL only)
    try:
        if is_postgresql():
            op.execute("CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias USING GIN (to_tsvector('simple', alias))")
            print("   ✅ Created GIN index for alias search")
    except Exception:
        print("   ⚠️  Could not create GIN index - non-Postgres or already exists")

    # 3) Backfill aliases from global_item.aka_names JSON if present
    if table_exists('global_item_alias') and table_exists('global_item'):
        try:
            op.execute("""
                INSERT INTO global_item_alias (global_item_id, alias)
                SELECT gi.id, trim(value::text, '"') AS alias
                FROM global_item gi,
                     json_array_elements(COALESCE(gi.aka_names, '[]'::json)) AS value
                WHERE value IS NOT NULL AND trim(value::text, '"') <> ''
                  AND NOT EXISTS (
                      SELECT 1 FROM global_item_alias 
                      WHERE global_item_id = gi.id AND alias = trim(value::text, '"')
                  )
            """)
            print("   ✅ Backfilled aliases from aka_names")
        except Exception:
            # Skip if JSON functions unsupported
            print("   ⚠️  Could not backfill aliases - JSON functions unsupported")

    # 4) Performance indexes on organization_id for core tables (create if missing)
    index_targets = [
        ('inventory_item', 'organization_id', 'ix_inventory_item_org'),
        ('inventory_lot', 'organization_id', 'ix_inventory_lot_org'),
        ('unified_inventory_history', 'organization_id', 'ix_unified_history_org'),
        ('recipe', 'organization_id', 'ix_recipe_org'),
        ('batch', 'organization_id', 'ix_batch_org'),
        ('user', 'organization_id', 'ix_user_org'),
    ]
    
    for table, column, ix_name in index_targets:
        if not table_exists(table):
            print(f"   ⚠️  Table {table} does not exist - skipping index {ix_name}")
            continue
        created = safe_create_index(ix_name, table, [column])
        if created:
            print(f"   ✅ Created index {ix_name}")
        else:
            print(f"   ✅ Index {ix_name} already exists or was skipped")

    # 5) Optional JSONB GIN index on global_item.aka_names for fallback search (PostgreSQL only)
    if table_exists('global_item') and is_postgresql():
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING GIN ((aka_names::jsonb))")
            print("   ✅ Created JSONB GIN index on aka_names")
        except Exception:
            print("   ⚠️  Could not create JSONB GIN index - non-Postgres or already exists")
    
    print("✅ Alias and indexes migration completed")


def downgrade():
    # Drop indexes (best-effort)
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aka_gin")
    except Exception:
        pass
    for ix in ['ix_user_org','ix_batch_org','ix_recipe_org','ix_unified_history_org','ix_inventory_lot_org','ix_inventory_item_org']:
        try:
            op.drop_index(ix)
        except Exception:
            pass
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_alias_tsv")
    except Exception:
        pass
    try:
        op.drop_table('global_item_alias')
    except Exception:
        pass

