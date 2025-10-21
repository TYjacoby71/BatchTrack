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

# Import PostgreSQL helpers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import (
    table_exists,
    column_exists,
    index_exists,
    safe_create_index,
    safe_add_column,
    is_postgresql,
)

revision = '20251009_3'
down_revision = '20251009_2'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Starting model alignment with PostgreSQL safety ===")

    try:
        # 1) Org-scoping indexes
        print("   Creating org-scoping indexes...")
        for table, col, ix in [
            ('user', 'organization_id', 'ix_user_org'),
            ('inventory_item', 'organization_id', 'ix_inventory_item_org'),
            ('inventory_lot', 'organization_id', 'ix_inventory_lot_org'),
            ('unified_inventory_history', 'organization_id', 'ix_unified_history_org'),
            ('recipe', 'organization_id', 'ix_recipe_org'),
            ('batch', 'organization_id', 'ix_batch_org'),
        ]:
            safe_create_index(ix, table, [col], unique=False, verbose=True)

        # 2) ProductCategory functional unique index
        print("   Creating product category indexes...")
        if table_exists('product_category'):
            try:
                bind = op.get_bind()
                # Use dialect-safe expression (avoid ::text cast)
                bind.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name))"))
                print("   ✅ Created product category functional index")
            except Exception as e:
                print(f"   ⚠️  Product category index creation failed: {e}")

        # 3) Product foreign key index
        safe_create_index('ix_product_category_id', 'product', ['category_id'], unique=False, verbose=True)

        # 4) Recipe computed columns and indexes
        print("   Processing recipe computed columns...")
        if table_exists('recipe'):
            # Check which computed columns already exist to avoid conflicts
            computed_cols = {
                'soap_superfat': ("((category_data ->> 'soap_superfat'))::numeric", sa.Numeric()),
                'soap_water_pct': ("((category_data ->> 'soap_water_pct'))::numeric", sa.Numeric()),
                'soap_lye_type': ("(category_data ->> 'soap_lye_type')", sa.Text()),
                'candle_fragrance_pct': ("((category_data ->> 'candle_fragrance_pct'))::numeric", sa.Numeric()),
                'candle_vessel_ml': ("((category_data ->> 'candle_vessel_ml'))::numeric", sa.Numeric()),
                'vessel_fill_pct': ("((category_data ->> 'vessel_fill_pct'))::numeric", sa.Numeric()),
                'baker_base_flour_g': ("((category_data ->> 'baker_base_flour_g'))::numeric", sa.Numeric()),
                'baker_water_pct': ("((category_data ->> 'baker_water_pct'))::numeric", sa.Numeric()),
                'baker_salt_pct': ("((category_data ->> 'baker_salt_pct'))::numeric", sa.Numeric()),
                'baker_yeast_pct': ("((category_data ->> 'baker_yeast_pct'))::numeric", sa.Numeric()),
                'cosm_emulsifier_pct': ("((category_data ->> 'cosm_emulsifier_pct'))::numeric", sa.Numeric()),
                'cosm_preservative_pct': ("((category_data ->> 'cosm_preservative_pct'))::numeric", sa.Numeric()),
            }

            for name, (expr, col_def) in computed_cols.items():
                if not column_exists('recipe', name):
                    try:
                        bind = op.get_bind()
                        col_type = "numeric" if isinstance(col_def, type) and issubclass(col_def, sa.Numeric) else "text"
                        bind.execute(text(f"ALTER TABLE recipe ADD COLUMN {name} {col_type} GENERATED ALWAYS AS ({expr}) STORED"))
                        print(f"   ✅ Added computed column recipe.{name}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to add computed column recipe.{name}: {e}")
                        # Fallback using safe_add_column
                        safe_add_column('recipe', sa.Column(name, col_def, nullable=True), verbose=True)
                else:
                    print(f"   ✅ Column recipe.{name} already exists")

            # Recipe indexes
            recipe_indexes = [
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
            ]
            for ix, col in recipe_indexes:
                safe_create_index(ix, 'recipe', [col], verbose=True)

            # JSON/GIN index
            # Create JSONB GIN index only on PostgreSQL
            if is_postgresql():
                try:
                    bind = op.get_bind()
                    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING GIN ((category_data::jsonb))"))
                    print("   ✅ Created recipe GIN index")
                except Exception as e:
                    print(f"   ⚠️  Recipe GIN index creation failed: {e}")

        # 5) Batch computed columns and indexes
        print("   Processing batch computed columns...")
        if table_exists('batch'):
            batch_computed_cols = {
                'vessel_fill_pct': ("(((plan_snapshot -> 'category_extension') ->> 'vessel_fill_pct'))::numeric", sa.Numeric()),
                'candle_fragrance_pct': ("(((plan_snapshot -> 'category_extension') ->> 'candle_fragrance_pct'))::numeric", sa.Numeric()),
                'candle_vessel_ml': ("(((plan_snapshot -> 'category_extension') ->> 'candle_vessel_ml'))::numeric", sa.Numeric()),
                'soap_superfat': ("(((plan_snapshot -> 'category_extension') ->> 'soap_superfat'))::numeric", sa.Numeric()),
                'soap_water_pct': ("(((plan_snapshot -> 'category_extension') ->> 'soap_water_pct'))::numeric", sa.Numeric()),
                'soap_lye_type': ("((plan_snapshot -> 'category_extension') ->> 'soap_lye_type')", sa.Text()),
                'baker_base_flour_g': ("(((plan_snapshot -> 'category_extension') ->> 'baker_base_flour_g'))::numeric", sa.Numeric()),
                'baker_water_pct': ("(((plan_snapshot -> 'category_extension') ->> 'baker_water_pct'))::numeric", sa.Numeric()),
                'baker_salt_pct': ("(((plan_snapshot -> 'category_extension') ->> 'baker_salt_pct'))::numeric", sa.Numeric()),
                'baker_yeast_pct': ("(((plan_snapshot -> 'category_extension') ->> 'baker_yeast_pct'))::numeric", sa.Numeric()),
                'cosm_emulsifier_pct': ("(((plan_snapshot -> 'category_extension') ->> 'cosm_emulsifier_pct'))::numeric", sa.Numeric()),
                'cosm_preservative_pct': ("(((plan_snapshot -> 'category_extension') ->> 'cosm_preservative_pct'))::numeric", sa.Numeric()),
            }

            for name, (expr, col_def) in batch_computed_cols.items():
                if not column_exists('batch', name):
                    try:
                        bind = op.get_bind()
                        col_type = "numeric" if isinstance(col_def, type) and issubclass(col_def, sa.Numeric) else "text"
                        bind.execute(text(f"ALTER TABLE batch ADD COLUMN {name} {col_type} GENERATED ALWAYS AS ({expr}) STORED"))
                        print(f"   ✅ Added computed column batch.{name}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to add computed column batch.{name}: {e}")
                        # Fallback using safe_add_column
                        safe_add_column('batch', sa.Column(name, col_def, nullable=True), verbose=True)
                else:
                    print(f"   ✅ Column batch.{name} already exists")

            # Batch indexes
            batch_indexes = [
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
            ]
            for ix, col in batch_indexes:
                safe_create_index(ix, 'batch', [col], verbose=True)

        # 6) BatchConsumable & ExtraBatchConsumable - add missing organization_id columns and indexes
        print("   Processing consumable tables...")
        consumable_tables = ['batch_consumable', 'extra_batch_consumable']

        for table in consumable_tables:
            if table_exists(table):
                # Add organization_id column if missing
                if not column_exists(table, 'organization_id'):
                    try:
                        safe_add_column(table, sa.Column('organization_id', sa.Integer(), nullable=True), verbose=True)
                        print(f"   ✅ Added organization_id to {table}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to add organization_id to {table}: {e}")
                else:
                    print(f"   ✅ organization_id already exists in {table}")

        # Now create indexes - but handle the organization_id column addition failure gracefully
        consumable_index_specs = [
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
        ]
        
        for table, indexes in consumable_index_specs:
            if table_exists(table):
                print(f"   Creating indexes for {table}...")
                for ix, col in indexes:
                    # Only create index if the column actually exists
                    if column_exists(table, col):
                        safe_create_index(ix, table, [col], verbose=True)
                    else:
                        print(f"   ⚠️  Column {col} doesn't exist in {table} - skipping index {ix}")
            else:
                print(f"   ⚠️  Table {table} doesn't exist - skipping indexes")

        # 7) Global Item alias table and indexes
        print("   Processing global item alias table...")
        if not table_exists('global_item_alias') and table_exists('global_item'):
            try:
                op.create_table(
                    'global_item_alias',
                    sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
                    sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('alias', sa.Text(), nullable=False),
                )
                print("   ✅ Created global_item_alias table")
            except Exception as e:
                print(f"   ⚠️  Failed to create global_item_alias table: {e}")

        if table_exists('global_item_alias'):
            safe_create_index('ix_global_item_alias_alias', 'global_item_alias', ['alias'], verbose=True)
            safe_create_index('ix_global_item_alias_global_item_id', 'global_item_alias', ['global_item_id'], verbose=True)
            if is_postgresql():
                try:
                    bind = op.get_bind()
                    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias USING GIN (to_tsvector('simple', alias))"))
                    print("   ✅ Created global_item_alias GIN index")
                except Exception as e:
                    print(f"   ⚠️  Global item alias GIN index creation failed: {e}")

        # 8) GlobalItem aka_names JSON/GIN
        if table_exists('global_item') and is_postgresql():
            try:
                bind = op.get_bind()
                bind.execute(text("CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING GIN ((aka_names::jsonb))"))
                print("   ✅ Created global_item aka_names GIN index")
            except Exception as e:
                print(f"   ⚠️  Global item aka_names GIN index creation failed: {e}")

        print("✅ Model alignment completed successfully")

    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        # Re-raise the exception to ensure Alembic knows the migration failed
        raise


def downgrade():
    # No destructive downgrades; these are model-owned performance objects.
    pass