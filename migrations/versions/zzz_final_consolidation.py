
"""Final consolidation migration - merge all heads

Revision ID: zzz_final_consolidation
Revises: 630aa4ce3717, clean_merge_final, make_organization_id_nullable, remove_default_units
Create Date: 2025-07-18 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'zzz_final_consolidation'
down_revision = ('630aa4ce3717', 'clean_merge_final', 'make_organization_id_nullable', 'remove_default_units')
branch_labels = None
depends_on = None

def upgrade():
    # This is a consolidation migration - no operations needed
    pass

def downgrade():
    # This is a consolidation migration - no operations needed  
    pass
