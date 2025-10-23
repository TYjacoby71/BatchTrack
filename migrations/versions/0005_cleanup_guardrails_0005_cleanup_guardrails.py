
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

    # Nullability constraints now handled in base schema (0001)
    # This migration now only handles PostgreSQL-specific performance optimizations


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
    
    # No constraint changes to reverse - only PostgreSQL indexes dropped above
    pass
