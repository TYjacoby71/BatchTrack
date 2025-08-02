"""fix inventory history constraints

Revision ID: fix_inventory_history_constraints
Revises: 8b7aa70df87d
Create Date: 2025-08-02 06:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers
revision = 'fix_inv_hist_constraints'
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

    # Drop legacy columns that don't exist in current model
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        if 'quantity_before' in column_names:
            batch_op.drop_column('quantity_before')

        if 'quantity_after' in column_names:
            batch_op.drop_column('quantity_after')

        if 'reason' in column_names:
            batch_op.drop_column('reason')

        # Keep user_id but make it nullable (it exists as created_by in model)
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

    # Re-add the dropped columns
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        if 'quantity_before' not in column_names:
            batch_op.add_column(sa.Column('quantity_before', sa.Float(), nullable=True))

        if 'quantity_after' not in column_names:
            batch_op.add_column(sa.Column('quantity_after', sa.Float(), nullable=True))

        if 'reason' not in column_names:
            batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))

        # Restore user_id constraint
        if 'user_id' in column_names:
            batch_op.alter_column('user_id',
                        existing_type=sa.Integer(),
                        nullable=False)