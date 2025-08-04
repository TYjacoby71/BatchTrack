
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
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('remaining_quantity', sa.Float(), nullable=False, default=0.0),
            sa.Column('change_type', sa.String(50), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('batch_id', sa.Integer(), nullable=True),
            sa.Column('used_for_batch_id', sa.Integer(), nullable=True),
            sa.Column('cost_per_unit', sa.Float(), nullable=True),
            sa.Column('unit', sa.String(20), nullable=True),
            sa.Column('fifo_code', sa.String(50), nullable=True),
            sa.Column('expiration_date', sa.Date(), nullable=True),
            sa.Column('source', sa.String(100), nullable=True),
            sa.Column('fifo_reference_id', sa.String(100), nullable=True),
            sa.Column('order_id', sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        print("   ✅ Created inventory_history table")
    else:
        print("   ✅ inventory_history table already exists")
    
    # 2. Add missing columns if they don't exist
    missing_columns = [
        ('remaining_quantity', sa.Float(), False, 0.0),
        ('fifo_code', sa.String(50), True, None),
        ('expiration_date', sa.Date(), True, None),
        ('source', sa.String(100), True, None),
        ('fifo_reference_id', sa.String(100), True, None),
        ('order_id', sa.Integer(), True, None),
    ]
    
    for col_name, col_type, nullable, default in missing_columns:
        if not column_exists('inventory_history', col_name):
            print(f"   Adding missing column: {col_name}")
            if default is not None:
                op.add_column('inventory_history', sa.Column(col_name, col_type, nullable=nullable, default=default))
            else:
                op.add_column('inventory_history', sa.Column(col_name, col_type, nullable=nullable))
    
    # 3. Fix remaining_quantity for existing records
    print("   Updating remaining_quantity for existing records...")
    bind.execute(text("""
        UPDATE inventory_history 
        SET remaining_quantity = CASE 
            WHEN change_type IN ('purchase', 'adjustment_increase', 'finished_batch', 'return', 'found') 
            THEN quantity 
            ELSE 0.0 
        END 
        WHERE remaining_quantity IS NULL OR remaining_quantity = 0
    """))
    
    # 4. Add constraints if they don't exist
    constraints_to_add = [
        ('ck_inventory_history_quantity_positive', 'quantity > 0'),
        ('ck_inventory_history_remaining_quantity_non_negative', 'remaining_quantity >= 0'),
        ('ck_inventory_history_remaining_quantity_lte_quantity', 'remaining_quantity <= quantity'),
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
    
    # 5. Create indexes for performance
    try:
        op.create_index('idx_inventory_history_item_remaining', 'inventory_history', 
                       ['inventory_item_id', 'remaining_quantity'])
        print("   ✅ Created performance index on inventory_item_id, remaining_quantity")
    except Exception as e:
        print(f"   ⚠️  Index may already exist: {e}")
    
    try:
        op.create_index('idx_inventory_history_fifo_code', 'inventory_history', ['fifo_code'])
        print("   ✅ Created index on fifo_code")
    except Exception as e:
        print(f"   ⚠️  Index may already exist: {e}")
    
    print("✅ Inventory history constraints fixed successfully")


def downgrade():
    """Remove the constraints and indexes added in upgrade"""
    print("=== Reverting inventory history constraints ===")
    
    # Remove constraints
    constraints_to_remove = [
        'ck_inventory_history_quantity_positive',
        'ck_inventory_history_remaining_quantity_non_negative', 
        'ck_inventory_history_remaining_quantity_lte_quantity',
    ]
    
    for constraint_name in constraints_to_remove:
        try:
            op.drop_constraint(constraint_name, 'inventory_history', type_='check')
            print(f"   ✅ Removed constraint: {constraint_name}")
        except Exception as e:
            print(f"   ⚠️  Could not remove constraint {constraint_name}: {e}")
    
    # Remove indexes
    try:
        op.drop_index('idx_inventory_history_item_remaining', 'inventory_history')
        print("   ✅ Removed index on inventory_item_id, remaining_quantity")
    except Exception as e:
        print(f"   ⚠️  Could not remove index: {e}")
    
    try:
        op.drop_index('idx_inventory_history_fifo_code', 'inventory_history')
        print("   ✅ Removed index on fifo_code")
    except Exception as e:
        print(f"   ⚠️  Could not remove index: {e}")
    
    print("✅ Downgrade completed")
