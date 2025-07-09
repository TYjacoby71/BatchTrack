
"""Add customer column to reservation table

Revision ID: 6e0c5e2e1c48
Revises: 9bc15ea2061a
Create Date: 2025-07-09 23:26:09.075172

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e0c5e2e1c48'
down_revision = '9bc15ea2061a'
branch_labels = None
depends_on = None


def upgrade():
    # Add customer column to existing reservation table
    with op.batch_alter_table('reservation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer', sa.String(length=128), nullable=True))


def downgrade():
    # Remove customer column
    with op.batch_alter_table('reservation', schema=None) as batch_op:
        batch_op.drop_column('customer')
