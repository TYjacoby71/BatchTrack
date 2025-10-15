"""Add batch_id to inventory_lot table

Revision ID: add_batch_id_to_inventory_lot
Revises: add_affected_lot_id_simple
Create Date: 2025-08-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_batch_id_to_inventory_lot'
down_revision = 'add_affected_lot_id_simple'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def foreign_key_exists(table_name, constraint_name):
    """Check if a foreign key constraint exists"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == constraint_name for fk in fks)
    except:
        return False

def upgrade():
    """Add batch_id to inventory_lot table"""
    print("=== Adding batch_id to inventory_lot table ===")

    # Check if the column already exists
    if not column_exists('inventory_lot', 'batch_id'):
        print("   Adding batch_id column...")
        with op.batch_alter_table('inventory_lot', schema=None) as batch_op:
            batch_op.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
        print("   ✅ batch_id column added")
    else:
        print("   ✅ batch_id column already exists - skipping")

    # Check if the foreign key constraint exists
    if not foreign_key_exists('inventory_lot', 'fk_inventory_lot_batch_id'):
        print("   Adding foreign key constraint...")
        with op.batch_alter_table('inventory_lot', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_inventory_lot_batch_id', 'batch', ['batch_id'], ['id'])
        print("   ✅ Foreign key constraint added")
    else:
        print("   ✅ Foreign key constraint already exists - skipping")

    print("✅ batch_id migration completed")


def downgrade():
    """Remove batch_id from inventory_lot table"""
    print("=== Removing batch_id from inventory_lot table ===")
    
    if not table_exists('inventory_lot'):
        print("   ⚠️  inventory_lot table does not exist - skipping")
        return

    # Remove foreign key constraint if it exists
    if foreign_key_exists('inventory_lot', 'fk_inventory_lot_batch_id'):
        print("   Removing foreign key constraint...")
        try:
            with op.batch_alter_table('inventory_lot', schema=None) as batch_op:
                batch_op.drop_constraint('fk_inventory_lot_batch_id', type_='foreignkey')
            print("   ✅ Foreign key constraint removed")
        except Exception as e:
            print(f"   ⚠️  Error removing foreign key: {e}")
    else:
        print("   ✅ Foreign key constraint doesn't exist - skipping")

    # Remove column if it exists
    if column_exists('inventory_lot', 'batch_id'):
        print("   Removing batch_id column...")
        try:
            with op.batch_alter_table('inventory_lot', schema=None) as batch_op:
                batch_op.drop_column('batch_id')
            print("   ✅ batch_id column removed")
        except Exception as e:
            print(f"   ⚠️  Error removing column: {e}")
    else:
        print("   ✅ batch_id column doesn't exist - skipping")

    print("✅ batch_id downgrade completed")