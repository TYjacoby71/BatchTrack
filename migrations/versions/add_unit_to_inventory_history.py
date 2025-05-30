
"""Add unit field to inventory_history

Revision ID: add_unit_to_history
Revises: 4ff7f4b5ea62
Create Date: 2025-05-30 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_unit_to_history'
down_revision = '4ff7f4b5ea62'
branch_labels = None
depends_on = None

def upgrade():
    # Add the unit column
    op.add_column('inventory_history', sa.Column('unit', sa.String(32), nullable=True))
    
    # Backfill existing records with the current unit from inventory_item
    connection = op.get_bind()
    connection.execute("""
        UPDATE inventory_history 
        SET unit = (
            SELECT unit 
            FROM inventory_item 
            WHERE inventory_item.id = inventory_history.inventory_item_id
        )
        WHERE unit IS NULL
    """)
    
    # Make the column non-nullable after backfill
    op.alter_column('inventory_history', 'unit', nullable=False)

def downgrade():
    op.drop_column('inventory_history', 'unit')
