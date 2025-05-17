
"""Update inventory change types

Revision ID: update_inventory_types
Revises: 923b23b7c7ba
Create Date: 2025-05-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'update_inventory_types'
down_revision = '923b23b7c7ba'
branch_labels = None
depends_on = None

def upgrade():
    # Convert 'use' to 'batch'
    op.execute(text("UPDATE inventory_history SET change_type = 'batch' WHERE change_type = 'use'"))
    # Convert 'manual' to 'recount'
    op.execute(text("UPDATE inventory_history SET change_type = 'recount' WHERE change_type = 'manual'"))

def downgrade():
    # Convert 'batch' back to 'use'
    op.execute(text("UPDATE inventory_history SET change_type = 'use' WHERE change_type = 'batch'"))
    # Convert 'recount' back to 'manual'
    op.execute(text("UPDATE inventory_history SET change_type = 'manual' WHERE change_type = 'recount'"))
