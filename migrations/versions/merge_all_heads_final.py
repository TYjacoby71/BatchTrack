
"""Merge all heads final

Revision ID: merge_all_heads_final
Revises: drop_role_id_column, remove_org_timezone, rename_multiplier_cf
Create Date: 2025-07-19 00:56:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_all_heads_final'
down_revision = ('drop_role_id_column', 'remove_org_timezone', 'rename_multiplier_cf')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration - no operations needed
    pass

def downgrade():
    # This is a merge migration - no operations needed
    pass
