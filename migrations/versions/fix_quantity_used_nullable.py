
"""fix quantity_used nullable

Revision ID: fix_quantity_used_nullable
Revises: 068534518f6c
Create Date: 2025-06-05 23:44:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_quantity_used_nullable'
down_revision = '068534518f6c'
branch_labels = None
depends_on = None


def upgrade():
    # Make quantity_used column nullable
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.alter_column('quantity_used',
                             existing_type=sa.Float(),
                             nullable=True)


def downgrade():
    # Make quantity_used column not nullable (this might fail if there are NULL values)
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.alter_column('quantity_used',
                             existing_type=sa.Float(),
                             nullable=False)
