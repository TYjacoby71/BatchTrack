
"""Add Whop integration fields to Organization

Revision ID: whop_integration
Revises: 132971c1d456
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'whop_integration'
down_revision = '132971c1d456'
branch_labels = None
depends_on = None

def upgrade():
    # Add Whop integration fields to organization table
    op.add_column('organization', sa.Column('whop_license_key', sa.String(128), nullable=True))
    op.add_column('organization', sa.Column('whop_product_tier', sa.String(32), nullable=True))
    op.add_column('organization', sa.Column('whop_verified', sa.Boolean(), default=False))

def downgrade():
    # Remove Whop integration fields
    op.drop_column('organization', 'whop_verified')
    op.drop_column('organization', 'whop_product_tier')
    op.drop_column('organization', 'whop_license_key')
