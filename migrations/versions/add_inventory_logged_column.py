
"""add inventory logged column

Revision ID: add_inventory_logged_column
Revises: 73212808b003
Create Date: 2025-05-03 01:25:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_inventory_logged_column'
down_revision = '73212808b003'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('batch', schema=None) as batch_op:
        batch_op.add_column(sa.Column('inventory_logged', sa.Boolean(), nullable=True))

def downgrade():
    with op.batch_alter_table('batch', schema=None) as batch_op:
        batch_op.drop_column('inventory_logged')
