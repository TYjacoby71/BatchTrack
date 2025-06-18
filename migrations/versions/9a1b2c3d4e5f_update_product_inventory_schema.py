
"""Update product_inventory schema

Revision ID: 9a1b2c3d4e5f
Revises: 8f193ade2856
Create Date: 2025-06-18 01:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '9a1b2c3d4e5f'
down_revision = '8f193ade2856'
branch_labels = None
depends_on = None

def upgrade():
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check existing columns in product_inventory table
    existing_columns = [col['name'] for col in inspector.get_columns('product_inventory')]
    
    # Update product_inventory table structure
    with op.batch_alter_table('product_inventory', schema=None) as batch_op:
        # Add variant_id if it doesn't exist
        if 'variant_id' not in existing_columns:
            batch_op.add_column(sa.Column('variant_id', sa.Integer(), nullable=False))
            batch_op.create_foreign_key('fk_product_inventory_variant_id', 'product_variation', ['variant_id'], ['id'])
        
        # Remove old columns if they exist
        if 'variant' in existing_columns:
            batch_op.drop_column('variant')
        if 'size_label' in existing_columns:
            batch_op.drop_column('size_label')
        if 'sku' in existing_columns:
            batch_op.drop_column('sku')
        if 'container_id' in existing_columns:
            batch_op.drop_column('container_id')
        if 'notes' in existing_columns:
            batch_op.drop_column('notes')
        if 'timestamp' in existing_columns:
            batch_op.drop_column('timestamp')
        if 'batch_cost_per_unit' in existing_columns:
            batch_op.drop_column('batch_cost_per_unit')

def downgrade():
    # Reverse the changes
    with op.batch_alter_table('product_inventory', schema=None) as batch_op:
        # Add back old columns
        batch_op.add_column(sa.Column('variant', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('size_label', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('sku', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('container_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('timestamp', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('batch_cost_per_unit', sa.Float(), nullable=True))
        
        # Remove variant_id
        try:
            batch_op.drop_constraint('fk_product_inventory_variant_id', type_='foreignkey')
        except Exception:
            pass
        batch_op.drop_column('variant_id')
