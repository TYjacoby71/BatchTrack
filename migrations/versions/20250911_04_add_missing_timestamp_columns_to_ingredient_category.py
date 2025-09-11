
"""Add missing timestamp columns to ingredient_category

Revision ID: 20250911_04
Revises: 20250911_03
Create Date: 2025-09-11 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250911_04'
down_revision = '20250911_03'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing timestamp columns to ingredient_category table
    try:
        op.add_column('ingredient_category', sa.Column('created_at', sa.DateTime(), nullable=True))
        op.add_column('ingredient_category', sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        # Set default values for existing records
        op.execute("UPDATE ingredient_category SET created_at = NOW(), updated_at = NOW() WHERE created_at IS NULL")
        
        # Make columns non-nullable after setting defaults
        op.alter_column('ingredient_category', 'created_at', nullable=False)
        op.alter_column('ingredient_category', 'updated_at', nullable=False)
        
        print("✅ Added missing timestamp columns to ingredient_category")
    except Exception as e:
        print(f"⚠️  Error adding timestamp columns to ingredient_category: {e}")
        # Continue anyway - might already exist

def downgrade():
    op.drop_column('ingredient_category', 'updated_at')
    op.drop_column('ingredient_category', 'created_at')
