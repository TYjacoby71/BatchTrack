
"""Final consolidation migration - clean slate

Revision ID: final_consolidation_2025
Revises: add_trial_billing_fields
Create Date: 2025-07-19 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'final_consolidation_2025'
down_revision = '7fbece7d5bfd'
branch_labels = None
depends_on = None

def upgrade():
    # This is the final consolidation - no operations needed
    # All schema changes are already applied
    pass

def downgrade():
    # This is the final consolidation - no operations needed
    pass
