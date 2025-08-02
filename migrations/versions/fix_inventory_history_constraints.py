
"""fix inventory history constraints

Revision ID: fix_inventory_history_constraints
Revises: 8b7aa70df87d
Create Date: 2025-08-02 06:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_inventory_history_constraints'
down_revision = '8b7aa70df87d'
branch_labels = None
depends_on = None

def upgrade():
    # Remove NOT NULL constraints from legacy columns that aren't used
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        # Make quantity_before nullable (legacy column, not used in current model)
        batch_op.alter_column('quantity_before',
                    existing_type=sa.Float(),
                    nullable=True)
        
        # Make quantity_after nullable (legacy column, not used in current model)  
        batch_op.alter_column('quantity_after',
                    existing_type=sa.Float(),
                    nullable=True)
        
        # Make reason nullable (legacy column, now using 'note')
        batch_op.alter_column('reason',
                    existing_type=sa.Text(),
                    nullable=True)
        
        # Make user_id nullable (should use created_by instead)
        batch_op.alter_column('user_id',
                    existing_type=sa.Integer(),
                    nullable=True)

def downgrade():
    # Restore NOT NULL constraints (if needed for rollback)
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.alter_column('quantity_before',
                    existing_type=sa.Float(),
                    nullable=False)
        
        batch_op.alter_column('quantity_after',
                    existing_type=sa.Float(),
                    nullable=False)
        
        batch_op.alter_column('reason',
                    existing_type=sa.Text(),
                    nullable=False)
        
        batch_op.alter_column('user_id',
                    existing_type=sa.Integer(),
                    nullable=False)
