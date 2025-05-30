
"""Add unit field to inventory_history

Revision ID: add_unit_to_history
Revises: 8f63b86dc675
Create Date: 2025-05-30 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '8f63b86dc675'
branch_labels = None
depends_on = None

def upgrade():
    # Add unit column to inventory_history
    op.add_column('inventory_history', sa.Column('unit', sa.String(32), nullable=True))
    
    # Backfill existing records with their inventory item's current unit
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE inventory_history 
        SET unit = (
            SELECT inventory_item.unit 
            FROM inventory_item 
            WHERE inventory_item.id = inventory_history.inventory_item_id
        )
        WHERE unit IS NULL
    """))
    
    # Make the column non-nullable after backfill
    op.alter_column('inventory_history', 'unit', nullable=False)

def downgrade():
    op.drop_column('inventory_history', 'unit')
