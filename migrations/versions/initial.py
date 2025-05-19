
"""Initial migration

Revision ID: initial
Revises: 
Create Date: 2025-05-19 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'update_inventory_types'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create all tables from models.py
    pass

def downgrade():
    # Drop all tables
    pass
