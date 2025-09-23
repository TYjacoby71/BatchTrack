"""
Add portioning_data JSON to recipe and batch

Revision ID: 20250923_03_add_portioning_json
Revises: 20250923_02_add_category_to_product_and_recipe
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250923_03_add_portioning_json'
down_revision = '20250923_02_add_category_to_product_and_recipe'
branch_labels = None
depends_on = None


def upgrade():
    # Add JSON columns as nullable
    with op.batch_alter_table('recipe') as batch_op:
        try:
            batch_op.add_column(sa.Column('portioning_data', sa.JSON(), nullable=True))
        except Exception:
            pass

    with op.batch_alter_table('batch') as batch_op:
        try:
            batch_op.add_column(sa.Column('portioning_data', sa.JSON(), nullable=True))
        except Exception:
            pass


def downgrade():
    try:
        with op.batch_alter_table('batch') as batch_op:
            batch_op.drop_column('portioning_data')
    except Exception:
        pass

    try:
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.drop_column('portioning_data')
    except Exception:
        pass

