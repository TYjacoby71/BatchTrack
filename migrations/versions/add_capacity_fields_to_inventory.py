
"""Add capacity fields to inventory items and migrate container data

Revision ID: add_capacity_fields
Revises: [current_head]
Create Date: 2025-09-01 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_capacity_fields'
down_revision = None  # Set this to current head
branch_labels = None
depends_on = None


def upgrade():
    # Add new capacity columns
    op.add_column('inventory_item', sa.Column('capacity', sa.Float(), nullable=True))
    op.add_column('inventory_item', sa.Column('capacity_unit', sa.String(32), nullable=True))
    
    # Migrate existing container data
    connection = op.get_bind()
    connection.execute("""
        UPDATE inventory_item 
        SET capacity = storage_amount, 
            capacity_unit = storage_unit 
        WHERE type = 'container' 
        AND storage_amount IS NOT NULL
    """)


def downgrade():
    op.drop_column('inventory_item', 'capacity_unit')
    op.drop_column('inventory_item', 'capacity')
