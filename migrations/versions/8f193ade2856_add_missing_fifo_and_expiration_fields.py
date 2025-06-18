
"""Add missing FIFO and expiration fields

Revision ID: 8f193ade2856
Revises: e2fac90b4ab4
Create Date: 2025-06-18 01:00:00.544975

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f193ade2856'
down_revision = 'e2fac90b4ab4'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing fifo_code column to inventory_history
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fifo_code', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
        # Add foreign key constraint in batch mode for SQLite compatibility
        batch_op.create_foreign_key('fk_inventory_history_batch_id', 'batch', ['batch_id'], ['id'])


def downgrade():
    # Remove the added columns
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_inventory_history_batch_id', type_='foreignkey')
        batch_op.drop_column('batch_id')
        batch_op.drop_column('fifo_code')
