"""
Merge heads: containers and portioning chains

Revision ID: 20250929_01_merge_heads_inventory_and_portioning
Revises: 20250925_01_add_container_attributes, 20250925_03
Create Date: 2025-09-29
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_01_merge_heads_inventory_and_portioning'
down_revision = ('20250925_01_add_container_attributes', '20250925_03')
branch_labels = None
depends_on = None


def upgrade():
    # Merge migrations, no schema changes needed here
    pass


def downgrade():
    # Downgrade not supported for merge; no-op
    pass