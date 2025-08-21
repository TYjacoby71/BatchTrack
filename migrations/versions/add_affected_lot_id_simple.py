
"""Add affected_lot_id to unified_inventory_history

Revision ID: add_affected_lot_id_simple
Revises: create_inventory_lot
Create Date: 2025-08-21 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'add_affected_lot_id_simple'
down_revision = 'create_inventory_lot'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    """Add affected_lot_id column to unified_inventory_history"""
    
    # Only add the column if it doesn't exist
    if not column_exists('unified_inventory_history', 'affected_lot_id'):
        print("Adding affected_lot_id column...")
        op.add_column('unified_inventory_history', 
                     sa.Column('affected_lot_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint if inventory_lot table exists
    if table_exists('inventory_lot'):
        try:
            op.create_foreign_key(
                'fk_unified_inventory_history_affected_lot_id',
                'unified_inventory_history',
                'inventory_lot',
                ['affected_lot_id'],
                ['id']
            )
            print("Added foreign key constraint for affected_lot_id")
        except Exception as e:
            print(f"Warning: Could not add foreign key constraint: {e}")
    
    print("✅ Simple affected_lot_id migration completed")


def downgrade():
    """Remove affected_lot_id column"""
    try:
        op.drop_constraint('fk_unified_inventory_history_affected_lot_id', 
                          'unified_inventory_history', type_='foreignkey')
    except Exception as e:
        print(f"Warning: Could not drop foreign key constraint: {e}")
    
    if column_exists('unified_inventory_history', 'affected_lot_id'):
        op.drop_column('unified_inventory_history', 'affected_lot_id')
    
    print("✅ Downgrade completed")
