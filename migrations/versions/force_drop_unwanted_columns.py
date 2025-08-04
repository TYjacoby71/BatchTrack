
"""force drop unwanted columns

Revision ID: 1a2b3c4d5e6f
Revises: 9d2a5c7f8b1e
Create Date: 2025-08-04 04:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = '9d2a5c7f8b1e'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(op.get_bind())
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def upgrade():
    """Force drop unwanted columns from inventory_history"""
    print("=== Force dropping unwanted columns ===")
    
    bind = op.get_bind()
    
    # List of columns to remove
    unwanted_columns = ['quantity_before', 'quantity_after', 'reason', 'user_id']
    
    for column_name in unwanted_columns:
        if column_exists('inventory_history', column_name):
            print(f"   Attempting to drop column: {column_name}")
            
            try:
                # First, try to drop any constraints on this column
                bind.execute(text(f"""
                    DO $$ 
                    DECLARE 
                        constraint_name text;
                    BEGIN
                        FOR constraint_name IN 
                            SELECT conname FROM pg_constraint 
                            WHERE conrelid = 'inventory_history'::regclass 
                            AND contype IN ('c', 'f', 'u')
                        LOOP
                            BEGIN
                                EXECUTE 'ALTER TABLE inventory_history DROP CONSTRAINT IF EXISTS ' || constraint_name || ' CASCADE';
                            EXCEPTION
                                WHEN OTHERS THEN NULL;
                            END;
                        END LOOP;
                    END $$;
                """))
                print(f"   ✅ Dropped constraints for {column_name}")
            except Exception as e:
                print(f"   ⚠️  Could not drop constraints for {column_name}: {e}")
            
            try:
                # Drop the column
                bind.execute(text(f"ALTER TABLE inventory_history DROP COLUMN IF EXISTS {column_name} CASCADE"))
                print(f"   ✅ Dropped column: {column_name}")
            except Exception as e:
                print(f"   ❌ Failed to drop {column_name}: {e}")
        else:
            print(f"   ℹ️  Column {column_name} does not exist")
    
    # Ensure required columns exist with proper defaults
    required_columns = [
        ('remaining_quantity', 'FLOAT DEFAULT 0.0'),
        ('fifo_code', 'VARCHAR(50)'),
        ('expiration_date', 'DATE'),
        ('fifo_reference_id', 'INTEGER'),
        ('quantity_used', 'FLOAT DEFAULT 0.0'),
        ('is_perishable', 'BOOLEAN DEFAULT FALSE'),
        ('shelf_life_days', 'INTEGER'),
        ('created_by', 'INTEGER'),
        ('unit_cost', 'FLOAT'),
    ]
    
    for col_name, col_def in required_columns:
        if not column_exists('inventory_history', col_name):
            try:
                bind.execute(text(f"ALTER TABLE inventory_history ADD COLUMN {col_name} {col_def}"))
                print(f"   ✅ Added required column: {col_name}")
            except Exception as e:
                print(f"   ⚠️  Could not add {col_name}: {e}")
    
    print("=== Force drop completed ===")

def downgrade():
    """This is a destructive migration - no downgrade available"""
    print("=== No downgrade available for force drop ===")
    pass
