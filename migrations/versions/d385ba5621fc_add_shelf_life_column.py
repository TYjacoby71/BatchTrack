
"""Add shelf life column

Revision ID: d385ba5621fc
Revises: 
Create Date: 2025-05-21 15:31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd385ba5621fc'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('inventory_item', sa.Column('shelf_life_days', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('inventory_item', 'shelf_life_days')
