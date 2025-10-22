

"""0006 align schema with models

Revision ID: 0006_schema_alignment
Revises: 0005_cleanup_guardrails
Create Date: 2025-01-22 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_schema_alignment'
down_revision = '0005_cleanup_guardrails'
branch_labels = None
depends_on = None


def upgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite
    
    # Only add PostgreSQL-specific optimizations if we're actually on PostgreSQL
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
    
    # SQLite - no special indexes needed, schema should already match from 0001-0005
    elif is_sqlite():
        pass


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
    
    # SQLite - nothing to downgrade
    elif is_sqlite():
        pass

