
"""fix product_sku name column

Revision ID: fix_product_sku_name_column
Revises: c8f2e5a9b1d4
Create Date: 2025-08-08 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_product_sku_name_column'
down_revision = 'c8f2e5a9b1d4'
branch_labels = None
depends_on = None

def upgrade():
    # First, update any NULL or empty name values with sku_code as fallback
    op.execute("""
        UPDATE product_sku 
        SET name = COALESCE(NULLIF(name, ''), sku_code, 'Unnamed SKU')
        WHERE name IS NULL OR name = ''
    """)
    
    # Rename the column from name to sku_name
    op.alter_column('product_sku', 'name', new_column_name='sku_name')
    
    # Ensure it's NOT NULL
    op.alter_column('product_sku', 'sku_name', nullable=False)

def downgrade():
    # Rename back to name
    op.alter_column('product_sku', 'sku_name', new_column_name='name')
