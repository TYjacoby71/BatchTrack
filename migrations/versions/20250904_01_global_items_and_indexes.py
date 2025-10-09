
"""Global items table, link to inventory_item, and performance indexes

Revision ID: 20250904_01
Revises: add_reference_guide_integration  
Create Date: 2025-08-27 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '20250904_01'
down_revision = 'add_reference_guide_integration'
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
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(index_name):
    """Check if an index exists"""
    bind = op.get_bind()
    try:
        result = bind.execute(text("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE indexname = :index_name
        """), {"index_name": index_name})
        return result.scalar() > 0
    except Exception:
        return False

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists"""
    bind = op.get_bind()
    try:
        result = bind.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints 
            WHERE table_name = :table_name 
            AND constraint_name = :constraint_name
        """), {"table_name": table_name, "constraint_name": constraint_name})
        return result.scalar() > 0
    except Exception:
        return False

def add_column_if_not_exists(table_name, column_name, column_type, **kwargs):
    """Add a column only if it doesn't already exist"""
    if not column_exists(table_name, column_name):
        print(f"   Adding {column_name} column to {table_name}...")
        op.add_column(table_name, sa.Column(column_name, column_type, **kwargs))
        print(f"   ✅ Added {column_name} column to {table_name}")
        return True
    else:
        print(f"   ✅ {column_name} column already exists in {table_name}")
        return False

def create_index_if_not_exists(index_name, table_name, columns):
    """Create an index only if it doesn't already exist"""
    if not index_exists(index_name):
        print(f"   Creating index {index_name}...")
        op.create_index(index_name, table_name, columns)
        print(f"   ✅ Created index {index_name}")
        return True
    else:
        print(f"   ✅ Index {index_name} already exists")
        return False

def upgrade():
    """Global items table, link to inventory_item, and performance indexes"""
    print("=== Creating global_item table and indexes ===")
    
    # Create global_item table if it doesn't exist
    if not table_exists('global_item'):
        print("Creating global_item table...")
        op.create_table('global_item',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('item_type', sa.String(length=32), nullable=False),
            sa.Column('default_unit', sa.String(length=32), nullable=True),
            sa.Column('density', sa.Float(), nullable=True),
            sa.Column('capacity', sa.Float(), nullable=True),
            sa.Column('capacity_unit', sa.String(length=32), nullable=True),
            sa.Column('suggested_inventory_category_id', sa.Integer(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc')
        )
        print("   ✅ Created global_item table")
    else:
        print("   ✅ global_item table already exists")

    # Create indexes on global_item
    create_index_if_not_exists('ix_global_item_name', 'global_item', ['name'])
    create_index_if_not_exists('ix_global_item_item_type', 'global_item', ['item_type'])

    # Add global_item_id column to inventory_item
    add_column_if_not_exists('inventory_item', 'global_item_id', sa.Integer(), nullable=True)

    # Create index on inventory_item.global_item_id
    create_index_if_not_exists('ix_inventory_item_global_item_id', 'inventory_item', ['global_item_id'])

    # Add foreign key constraint if it doesn't exist
    if not constraint_exists('inventory_item', 'fk_inventory_item_global_item'):
        print("   Adding foreign key constraint...")
        op.create_foreign_key('fk_inventory_item_global_item', 'inventory_item', 'global_item', ['global_item_id'], ['id'])
        print("   ✅ Added foreign key constraint")
    else:
        print("   ✅ Foreign key constraint already exists")

    # Add performance indexes
    create_index_if_not_exists('ix_inventory_item_organization_id', 'inventory_item', ['organization_id'])
    create_index_if_not_exists('ix_inventory_item_type', 'inventory_item', ['item_type'])
    create_index_if_not_exists('ix_inventory_item_is_archived', 'inventory_item', ['is_archived'])

    # Add user.organization_id index if it doesn't exist
    create_index_if_not_exists('ix_user_organization_id', 'user', ['organization_id'])

    print("✅ Global items migration completed successfully")

def downgrade():
    """Remove global items table and related changes"""
    print("=== Removing global items table and indexes ===")
    
    # Drop indexes
    try:
        op.drop_index('ix_user_organization_id', table_name='user')
        print("   ✅ Dropped ix_user_organization_id")
    except Exception:
        print("   ℹ️  Index ix_user_organization_id doesn't exist")

    try:
        op.drop_index('ix_inventory_item_is_archived', table_name='inventory_item')
        print("   ✅ Dropped ix_inventory_item_is_archived")
    except Exception:
        print("   ℹ️  Index ix_inventory_item_is_archived doesn't exist")

    try:
        op.drop_index('ix_inventory_item_type', table_name='inventory_item')
        print("   ✅ Dropped ix_inventory_item_type")
    except Exception:
        print("   ℹ️  Index ix_inventory_item_type doesn't exist")

    try:
        op.drop_index('ix_inventory_item_organization_id', table_name='inventory_item')
        print("   ✅ Dropped ix_inventory_item_organization_id")
    except Exception:
        print("   ℹ️  Index ix_inventory_item_organization_id doesn't exist")

    # Drop foreign key constraint
    try:
        op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
        print("   ✅ Dropped foreign key constraint")
    except Exception:
        print("   ℹ️  Foreign key constraint doesn't exist")

    # Drop index and column
    try:
        op.drop_index('ix_inventory_item_global_item_id', table_name='inventory_item')
        print("   ✅ Dropped ix_inventory_item_global_item_id")
    except Exception:
        print("   ℹ️  Index ix_inventory_item_global_item_id doesn't exist")

    try:
        op.drop_column('inventory_item', 'global_item_id')
        print("   ✅ Dropped global_item_id column")
    except Exception:
        print("   ℹ️  Column global_item_id doesn't exist")

    # Drop global_item indexes
    try:
        op.drop_index('ix_global_item_item_type', table_name='global_item')
        print("   ✅ Dropped ix_global_item_item_type")
    except Exception:
        print("   ℹ️  Index ix_global_item_item_type doesn't exist")

    try:
        op.drop_index('ix_global_item_name', table_name='global_item')
        print("   ✅ Dropped ix_global_item_name")
    except Exception:
        print("   ℹ️  Index ix_global_item_name doesn't exist")

    # Drop global_item table
    if table_exists('global_item'):
        op.drop_table('global_item')
        print("   ✅ Dropped global_item table")
    else:
        print("   ℹ️  global_item table doesn't exist")

    print("✅ Global items downgrade completed")
