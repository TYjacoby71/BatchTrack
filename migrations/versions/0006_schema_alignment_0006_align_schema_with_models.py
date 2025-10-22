

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
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Schema should already match models from 0001-0005, just add PostgreSQL-specific optimizations
    if dialect == 'postgresql':
        # Add GIN indexes for JSON columns and text search
        try:
            op.execute('CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING gin ((aka_names::jsonb));')
        except:
            pass
        try:
            op.execute('CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING gin ((category_data::jsonb));')
        except:
            pass

        # Add text search index for global_item_alias using 'simple' config
        try:
            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias 
                USING gin(to_tsvector('simple', alias));
            """)
        except:
            pass

        # Add UNIQUE case-insensitive index for product_category names
        try:
            op.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name));')
        except:
            pass


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop PostgreSQL-specific indexes only
    if dialect == 'postgresql':
        try:
            op.drop_index('ix_product_category_lower_name', table_name='product_category')
        except:
            pass
        try:
            op.drop_index('ix_global_item_alias_tsv', table_name='global_item_alias')
        except:
            pass
        try:
            op.drop_index('ix_recipe_category_data_gin', table_name='recipe')
        except:
            pass
        try:
            op.drop_index('ix_global_item_aka_gin', table_name='global_item')
        except:
            pass

