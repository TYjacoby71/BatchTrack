
"""
Add organization_id column to recipe_consumable table

Revision ID: 20250908_01
Revises: 2025090502
Create Date: 2025-09-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250908_01'
down_revision = '2025090502'
branch_labels = None
depends_on = None


def upgrade():
    # Add organization_id column to recipe_consumable table
    try:
        op.add_column('recipe_consumable', sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True))
        op.create_index('ix_recipe_consumable_organization_id', 'recipe_consumable', ['organization_id'])
    except Exception as e:
        print(f"Warning: Could not add organization_id to recipe_consumable: {e}")


def downgrade():
    try:
        op.drop_index('ix_recipe_consumable_organization_id', table_name='recipe_consumable')
        op.drop_column('recipe_consumable', 'organization_id')
    except Exception as e:
        print(f"Warning: Could not remove organization_id from recipe_consumable: {e}")
