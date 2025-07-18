
"""Final consolidation of all migration heads

Revision ID: 999_final_consolidation
Revises: clean_merge_final, make_organization_id_nullable, remove_default_units
Create Date: 2025-07-18 22:25:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '999_final_consolidation'
down_revision = ('clean_merge_final', 'make_organization_id_nullable', 'remove_default_units')
branch_labels = None
depends_on = None

def upgrade():
    # This is a consolidation migration - no operations needed
    pass

def downgrade():
    # This is a consolidation migration - no operations needed  
    pass
