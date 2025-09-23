"""
Create product_category table

Revision ID: 20250923_01_create_product_category
Revises: 20250922_01_align_extras
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250923_01_create_product_category'
down_revision = '20250922_01_align_extras'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_name = 'product_category'
    existing_tables = inspector.get_table_names()
    if table_name not in existing_tables:
        op.create_table(
            table_name,
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False, unique=True, index=True),
            sa.Column('is_typically_portioned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )

    # Ensure index on lower(name) if supported
    try:
        op.create_index('ix_product_category_lower_name', table_name, [sa.text('lower(name)')], unique=True)
    except Exception:
        # Some backends (SQLite) do not support expression indexes; skip
        pass


def downgrade():
    try:
        op.drop_index('ix_product_category_lower_name')
    except Exception:
        pass
    try:
        op.drop_table('product_category')
    except Exception:
        pass

