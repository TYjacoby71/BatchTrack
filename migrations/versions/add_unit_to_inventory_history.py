
"""Add unit field to inventory_history

Revision ID: add_unit_to_history
Revises: 4ff7f4b5ea62
Create Date: 2025-05-30 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_unit_to_history'
down_revision = '8f63b86dc675'
branch_labels = None
depends_on = None

def upgrade():
    # Add is_archived column to inventory_item
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_archived', sa.Boolean(), nullable=True))
    
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
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.drop_column('is_archived')
