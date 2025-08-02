
"""fix inventory history constraints

Revision ID: fix_inventory_history_constraints
Revises: 8b7aa70df87d
Create Date: 2025-08-02 06:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers
revision = 'fix_inventory_history_constraints'
down_revision = '8b7aa70df87d'
branch_labels = None
depends_on = None

def upgrade():
    # Get the current connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get current columns in inventory_history table
    columns = inspector.get_columns('inventory_history')
    column_names = [col['name'] for col in columns]
    
    # Only attempt to alter columns that actually exist
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        # Make quantity_before nullable if it exists
        if 'quantity_before' in column_names:
            batch_op.alter_column('quantity_before',
                        existing_type=sa.Float(),
                        nullable=True)
        
        # Make quantity_after nullable if it exists  
        if 'quantity_after' in column_names:
            batch_op.alter_column('quantity_after',
                        existing_type=sa.Float(),
                        nullable=True)
        
        # Make reason nullable if it exists
        if 'reason' in column_names:
            batch_op.alter_column('reason',
                        existing_type=sa.Text(),
                        nullable=True)
        
        # Make user_id nullable if it exists
        if 'user_id' in column_names:
            batch_op.alter_column('user_id',
                        existing_type=sa.Integer(),
                        nullable=True)

def downgrade():
    # Get the current connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get current columns in inventory_history table
    columns = inspector.get_columns('inventory_history')
    column_names = [col['name'] for col in columns]
    
    # Only attempt to alter columns that actually exist
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        # Restore NOT NULL constraints only if columns exist
        if 'quantity_before' in column_names:
            batch_op.alter_column('quantity_before',
                        existing_type=sa.Float(),
                        nullable=False)
        
        if 'quantity_after' in column_names:
            batch_op.alter_column('quantity_after',
                        existing_type=sa.Float(),
                        nullable=False)
        
        if 'reason' in column_names:
            batch_op.alter_column('reason',
                        existing_type=sa.Text(),
                        nullable=False)
        
        if 'user_id' in column_names:
            batch_op.alter_column('user_id',
                        existing_type=sa.Integer(),
                        nullable=False)
