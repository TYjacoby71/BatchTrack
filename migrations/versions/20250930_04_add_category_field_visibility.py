"""Add visibility control fields for soap-making attributes to ingredient categories

Revision ID: 20250930_4
Revises: 20250930_3
Create Date: 2025-09-30 04:00:00

"""
from alembic import op
import sqlalchemy as sa
from migrations.postgres_helpers import safe_add_column, safe_drop_column


# revision identifiers, used by Alembic.
revision = '20250930_4'
down_revision = '20250930_3'
branch_labels = None
depends_on = None


def upgrade():
    """Add visibility control fields to ingredient categories"""
    print("=== Adding visibility control fields to ingredient_category ===")

    # Add visibility control fields for soap-making attributes
    safe_add_column('ingredient_category', sa.Column('show_saponification_value', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_iodine_value', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_melting_point', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_flash_point', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_ph_value', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_moisture_content', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_shelf_life_months', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_comedogenic_rating', sa.Boolean(), nullable=True, default=False))

    print("✅ Visibility control fields migration completed")


def downgrade():
    """Remove visibility control fields"""
    print("=== Removing visibility control fields from ingredient_category ===")

    safe_drop_column('ingredient_category', 'show_comedogenic_rating')
    safe_drop_column('ingredient_category', 'show_shelf_life_months')
    safe_drop_column('ingredient_category', 'show_moisture_content')
    safe_drop_column('ingredient_category', 'show_ph_value')
    safe_drop_column('ingredient_category', 'show_flash_point')
    safe_drop_column('ingredient_category', 'show_melting_point')
    safe_drop_column('ingredient_category', 'show_iodine_value')
    safe_drop_column('ingredient_category', 'show_saponification_value')

    print("✅ Visibility control fields removal completed")