
"""Update Default variants to Base variants

Revision ID: update_default_to_base
Revises: 8dfa489d825b
Create Date: 2024-06-04 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'update_default_to_base'
down_revision = '8dfa489d825b'
branch_labels = None
depends_on = None

def upgrade():
    # Update ProductInventory table
    op.execute("UPDATE product_inventory SET variant = 'Base' WHERE variant = 'Default' OR variant IS NULL")
    
    # Update ProductEvent table if it references variants
    op.execute("UPDATE product_event SET note = REPLACE(note, 'Default', 'Base') WHERE note LIKE '%Default%'")
    
    # Update ProductInventoryHistory table if it exists
    try:
        op.execute("UPDATE product_inventory_history SET note = REPLACE(note, 'Default', 'Base') WHERE note LIKE '%Default%'")
    except:
        # Table might not exist yet
        pass

def downgrade():
    # Revert Base variants back to Default
    op.execute("UPDATE product_inventory SET variant = 'Default' WHERE variant = 'Base'")
    op.execute("UPDATE product_event SET note = REPLACE(note, 'Base', 'Default') WHERE note LIKE '%Base%'")
    
    try:
        op.execute("UPDATE product_inventory_history SET note = REPLACE(note, 'Base', 'Default') WHERE note LIKE '%Base%'")
    except:
        pass
