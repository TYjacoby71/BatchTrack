"""Update product_inventory schema

Revision ID: 6c5156b13ff8
Revises: 9a1b2c3d4e5f
Create Date: 2025-06-18 01:09:24.921586

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '6c5156b13ff8'
down_revision = '9a1b2c3d4e5f'
branch_labels = None
depends_on = None

def upgrade():
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check existing columns in product_inventory table
    existing_columns = [col['name'] for col in inspector.get_columns('product_inventory')]
    
    # Add expiration tracking fields if they don't exist
    with op.batch_alter_table('product_inventory', schema=None) as batch_op:
        if 'is_perishable' not in existing_columns:
            batch_op.add_column(sa.Column('is_perishable', sa.Boolean(), default=False))
        if 'shelf_life_days' not in existing_columns:
            batch_op.add_column(sa.Column('shelf_life_days', sa.Integer(), nullable=True))
        if 'expiration_date' not in existing_columns:
            batch_op.add_column(sa.Column('expiration_date', sa.DateTime(), nullable=True))

def downgrade():
    # Remove the added columns
    with op.batch_alter_table('product_inventory', schema=None) as batch_op:
        batch_op.drop_column('expiration_date')
        batch_op.drop_column('shelf_life_days')
        batch_op.drop_column('is_perishable')
