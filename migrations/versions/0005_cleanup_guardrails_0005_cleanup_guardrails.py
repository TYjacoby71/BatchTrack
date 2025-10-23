
"""0005 cleanup guardrails

Revision ID: 0005_cleanup_guardrails
Revises: 0004_seed_presets
Create Date: 2025-10-21 20:29:06.302261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_cleanup_guardrails'
down_revision = '0004_seed_presets'
branch_labels = None
depends_on = None


def upgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite
    
    # Schema alignment fixes from 0006
    if is_postgresql():
        # Use proper transaction handling
        bind = op.get_bind()
        
        # Add GIN indexes for JSON columns and text search (PostgreSQL only)
        try:
            bind.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING gin ((aka_names::jsonb))'))
        except Exception:
            # Ignore if index already exists or JSON columns don't exist yet
            pass
        
        try:
            bind.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING gin ((category_data::jsonb))'))
        except Exception:
            pass

        # Add text search index for global_item_alias using 'simple' config
        try:
            bind.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias 
                USING gin(to_tsvector('simple', alias))
            """))
        except Exception:
            pass

        # Add UNIQUE case-insensitive index for product_category names
        try:
            bind.execute(sa.text('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name))'))
        except Exception:
            pass

    # Final nullability constraints from 0007
    # Harden boolean defaults to be portable (sa.true()/sa.false()) and not null where desired
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Backfill first
    op.execute(sa.text('UPDATE "user" SET is_active = false WHERE is_active IS NULL'))
    op.execute(sa.text('UPDATE role SET is_active = false WHERE is_active IS NULL'))
    op.execute(sa.text('UPDATE inventory_item SET is_active = true WHERE is_active IS NULL'))
    op.execute(sa.text('UPDATE inventory_item SET is_archived = false WHERE is_archived IS NULL'))
    op.execute(sa.text('UPDATE feature_flag SET enabled = false WHERE enabled IS NULL'))

    if dialect == 'sqlite':
        # Use batch mode for SQLite to emulate ALTER COLUMN
        with op.batch_alter_table('user') as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        with op.batch_alter_table('role') as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        with op.batch_alter_table('inventory_item') as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), server_default=sa.true(), nullable=False)
            batch_op.alter_column('is_archived', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        with op.batch_alter_table('feature_flag') as batch_op:
            batch_op.alter_column('enabled', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
    else:
        op.alter_column('user', 'is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        op.alter_column('role', 'is_active', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        op.alter_column('inventory_item', 'is_active', existing_type=sa.Boolean(), server_default=sa.true(), nullable=False)
        op.alter_column('inventory_item', 'is_archived', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)
        op.alter_column('feature_flag', 'enabled', existing_type=sa.Boolean(), server_default=sa.false(), nullable=False)


def downgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite
    
    # Drop PostgreSQL-specific indexes only
    if is_postgresql():
        bind = op.get_bind()
        
        # Drop indexes in reverse order
        index_drops = [
            'ix_product_category_lower_name',
            'ix_global_item_alias_tsv', 
            'ix_recipe_category_data_gin',
            'ix_global_item_aka_gin'
        ]
        
        for index_name in index_drops:
            try:
                bind.execute(sa.text(f'DROP INDEX IF EXISTS {index_name}'))
            except Exception:
                # Index might not exist, continue
                pass
    
    # Don't reverse the constraint changes - leave them hardened
    # This prevents the back-and-forth nullable changes that cause issues
    pass
