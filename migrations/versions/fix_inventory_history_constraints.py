
"""fix inventory history constraints

Revision ID: 9d2a5c7f8b1e
Revises: 8b7aa70df87d
Create Date: 2025-08-04 02:38:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = '9d2a5c7f8b1e'
down_revision = '8b7aa70df87d'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists in the database"""
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    inspector = inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table"""
    if not table_exists(table_name):
        return False
    try:
        inspector = inspect(op.get_bind())
        constraints = inspector.get_check_constraints(table_name)
        return any(c['name'] == constraint_name for c in constraints)
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table"""
    if not table_exists(table_name):
        return False
    try:
        inspector = inspect(op.get_bind())
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False


def upgrade():
    """Fix inventory history constraints and ensure proper data integrity"""
    print("=== Fixing inventory history constraints ===")
    
    bind = op.get_bind()
    
    # 1. First, ensure inventory_history table exists with all required columns
    if not table_exists('inventory_history'):
        print("   Creating inventory_history table...")
        op.create_table('inventory_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), nullable=False),
            sa.Column('quantity_change', sa.Float(), nullable=False),
            sa.Column('remaining_quantity', sa.Float(), nullable=False, default=0.0),
            sa.Column('change_type', sa.String(50), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('batch_id', sa.Integer(), nullable=True),
            sa.Column('used_for_batch_id', sa.Integer(), nullable=True),
            sa.Column('unit_cost', sa.Float(), nullable=True),
            sa.Column('unit', sa.String(32), nullable=True),
            sa.Column('fifo_code', sa.String(50), nullable=True),
            sa.Column('expiration_date', sa.Date(), nullable=True),
            sa.Column('fifo_reference_id', sa.Integer(), nullable=True),
            sa.Column('quantity_used', sa.Float(), default=0.0),
            sa.Column('is_perishable', sa.Boolean(), default=False),
            sa.Column('shelf_life_days', sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
            sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
            sa.ForeignKeyConstraint(['used_for_batch_id'], ['batch.id']),
            sa.ForeignKeyConstraint(['created_by'], ['user.id']),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'])
        )
        print("   ✅ Created inventory_history table")
        return
    
    print("   ✅ inventory_history table already exists")
    
    # 2. Drop unwanted quantity_before column if it exists
    if column_exists('inventory_history', 'quantity_before'):
        print("   Dropping unwanted quantity_before column...")
        try:
            # For PostgreSQL, we need to drop the column directly
            bind.execute(text("ALTER TABLE inventory_history DROP COLUMN IF EXISTS quantity_before CASCADE"))
            print("   ✅ Dropped quantity_before column using direct SQL")
        except Exception as e:
            print(f"   ⚠️  Direct SQL drop failed: {e}")
            try:
                # Use batch mode for SQLite compatibility
                with op.batch_alter_table('inventory_history', schema=None) as batch_op:
                    batch_op.drop_column('quantity_before')
                print("   ✅ Dropped quantity_before column using batch mode")
            except Exception as e2:
                print(f"   ⚠️  Batch mode failed: {e2}")
                # Force drop if batch mode fails
                try:
                    op.drop_column('inventory_history', 'quantity_before')
                    print("   ✅ Force dropped quantity_before column")
                except Exception as e3:
                    print(f"   ❌ All drop attempts failed: {e3}")
                    # If we can't drop it, at least make it nullable temporarily
                    try:
                        bind.execute(text("ALTER TABLE inventory_history ALTER COLUMN quantity_before DROP NOT NULL"))
                        print("   ⚠️  Made quantity_before nullable as fallback")
                    except Exception as e4:
                        print(f"   ❌ Could not even make column nullable: {e4}")
    
    # 3. Add missing columns if they don't exist
    missing_columns = [
        ('remaining_quantity', sa.Float(), False, 0.0),
        ('fifo_code', sa.String(50), True, None),
        ('expiration_date', sa.Date(), True, None),
        ('fifo_reference_id', sa.Integer(), True, None),
        ('quantity_used', sa.Float(), True, 0.0),
        ('is_perishable', sa.Boolean(), True, False),
        ('shelf_life_days', sa.Integer(), True, None),
    ]
    
    for col_name, col_type, nullable, default in missing_columns:
        if not column_exists('inventory_history', col_name):
            print(f"   Adding missing column: {col_name}")
            if default is not None:
                op.add_column('inventory_history', sa.Column(col_name, col_type, nullable=nullable, default=default))
            else:
                op.add_column('inventory_history', sa.Column(col_name, col_type, nullable=nullable))
    
    # 4. Update remaining_quantity for existing records where it's missing or zero
    print("   Updating remaining_quantity for existing records...")
    try:
        bind.execute(text("""
            UPDATE inventory_history 
            SET remaining_quantity = CASE 
                WHEN change_type IN ('purchase', 'adjustment_increase', 'finished_batch', 'return', 'found', 'manual_addition') 
                THEN ABS(quantity_change)
                ELSE 0.0 
            END 
            WHERE remaining_quantity IS NULL OR remaining_quantity = 0
        """))
        print("   ✅ Updated remaining_quantity values")
    except Exception as e:
        print(f"   ⚠️  Could not update remaining_quantity: {e}")
    
    # 5. Clean up any invalid data before adding constraints
    print("   Cleaning up invalid data...")
    try:
        # Fix any negative remaining quantities
        bind.execute(text("""
            UPDATE inventory_history 
            SET remaining_quantity = 0 
            WHERE remaining_quantity < 0
        """))
        
        # Fix any remaining quantities greater than absolute quantity change
        bind.execute(text("""
            UPDATE inventory_history 
            SET remaining_quantity = ABS(quantity_change)
            WHERE remaining_quantity > ABS(quantity_change) AND quantity_change > 0
        """))
        print("   ✅ Cleaned up invalid data")
    except Exception as e:
        print(f"   ⚠️  Could not clean up data: {e}")
    
    # 6. Add constraints if they don't exist
    constraints_to_add = [
        ('ck_inventory_history_remaining_quantity_non_negative', 'remaining_quantity >= 0'),
    ]
    
    for constraint_name, constraint_condition in constraints_to_add:
        if not constraint_exists('inventory_history', constraint_name):
            try:
                op.create_check_constraint(
                    constraint_name,
                    'inventory_history',
                    constraint_condition
                )
                print(f"   ✅ Added constraint: {constraint_name}")
            except Exception as e:
                print(f"   ⚠️  Could not add constraint {constraint_name}: {e}")
    
    # 7. Create indexes for performance if they don't exist
    indexes_to_add = [
        ('idx_inventory_history_item_remaining', ['inventory_item_id', 'remaining_quantity']),
        ('idx_inventory_history_fifo_code', ['fifo_code']),
        ('idx_inventory_history_timestamp', ['timestamp']),
    ]
    
    for index_name, columns in indexes_to_add:
        if not index_exists('inventory_history', index_name):
            try:
                op.create_index(index_name, 'inventory_history', columns)
                print(f"   ✅ Created index: {index_name}")
            except Exception as e:
                print(f"   ⚠️  Index may already exist: {e}")
    
    print("✅ Inventory history constraints fixed successfully")


def downgrade():
    """Remove the constraints and indexes added in upgrade"""
    print("=== Reverting inventory history constraints ===")
    
    # Remove constraints
    constraints_to_remove = [
        'ck_inventory_history_remaining_quantity_non_negative',
    ]
    
    for constraint_name in constraints_to_remove:
        try:
            op.drop_constraint(constraint_name, 'inventory_history', type_='check')
            print(f"   ✅ Removed constraint: {constraint_name}")
        except Exception as e:
            print(f"   ⚠️  Could not remove constraint {constraint_name}: {e}")
    
    # Remove indexes
    indexes_to_remove = [
        'idx_inventory_history_item_remaining',
        'idx_inventory_history_fifo_code', 
        'idx_inventory_history_timestamp',
    ]
    
    for index_name in indexes_to_remove:
        try:
            op.drop_index(index_name, 'inventory_history')
            print(f"   ✅ Removed index: {index_name}")
        except Exception as e:
            print(f"   ⚠️  Could not remove index: {e}")
    
    print("✅ Downgrade completed")
