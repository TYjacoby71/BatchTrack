
"""Add is_active column to inventory_item

Revision ID: add_is_active_column
Revises: 6c5156b13ff8
Create Date: 2025-06-18 01:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_is_active_column'
down_revision = '6c5156b13ff8'
branch_labels = None
depends_on = None

def upgrade():
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check existing columns in inventory_item table
    existing_columns = [col['name'] for col in inspector.get_columns('inventory_item')]
    
    # Add is_active column if it doesn't exist
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        if 'is_active' not in existing_columns:
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), default=True))
            
    # Update existing records to have is_active = True
    conn.execute(sa.text("UPDATE inventory_item SET is_active = 1 WHERE is_active IS NULL"))

def downgrade():
    # Remove the added column
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.drop_column('is_active')
