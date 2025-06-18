
"""Add missing FIFO and expiration fields

Revision ID: 8f193ade2856
Revises: e2fac90b4ab4
Create Date: 2025-06-18 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '8f193ade2856'
down_revision = 'e2fac90b4ab4'
branch_labels = None
depends_on = None


def upgrade():
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check existing columns in inventory_history table
    existing_columns = [col['name'] for col in inspector.get_columns('inventory_history')]
    
    # Add columns to inventory_history if they don't exist
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        if 'fifo_code' not in existing_columns:
            batch_op.add_column(sa.Column('fifo_code', sa.String(length=32), nullable=True))
        if 'batch_id' not in existing_columns:
            batch_op.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint if batch_id column was added
    if 'batch_id' not in existing_columns:
        try:
            op.create_foreign_key('fk_inventory_history_batch_id', 'inventory_history', 'batch', ['batch_id'], ['id'])
        except Exception:
            # If foreign key creation fails, continue without it
            pass


def downgrade():
    # Remove foreign key constraint first
    try:
        op.drop_constraint('fk_inventory_history_batch_id', 'inventory_history', type_='foreignkey')
    except Exception:
        pass
    
    # Remove the added columns
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.drop_column('batch_id')
        batch_op.drop_column('fifo_code')
