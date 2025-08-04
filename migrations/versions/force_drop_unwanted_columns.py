
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

def get_database_type():
    """Determine if we're using SQLite or PostgreSQL"""
    bind = op.get_bind()
    return bind.dialect.name

def upgrade():
    """Force drop unwanted columns from inventory_history"""
    print("=== Force dropping unwanted columns ===")
    
    bind = op.get_bind()
    db_type = get_database_type()
    print(f"   Database type detected: {db_type}")
    
    # List of columns to remove
    unwanted_columns = ['quantity_before', 'quantity_after', 'reason', 'user_id']
    
    for column_name in unwanted_columns:
        if column_exists('inventory_history', column_name):
            print(f"   Attempting to drop column: {column_name}")
            
            # Handle constraint dropping based on database type
            if db_type == 'postgresql':
                try:
                    # PostgreSQL-specific constraint dropping
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
                    print(f"   ✅ Dropped constraints for {column_name} (PostgreSQL)")
                except Exception as e:
                    print(f"   ⚠️  Could not drop constraints for {column_name}: {e}")
            
            # Drop the column based on database type
            try:
                if db_type == 'postgresql':
                    # PostgreSQL supports IF EXISTS
                    bind.execute(text(f"ALTER TABLE inventory_history DROP COLUMN IF EXISTS {column_name} CASCADE"))
                    print(f"   ✅ Dropped column: {column_name} (PostgreSQL)")
                elif db_type == 'sqlite':
                    # SQLite doesn't support IF EXISTS or CASCADE, and doesn't support DROP COLUMN in older versions
                    # We need to use batch mode for SQLite
                    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
                        batch_op.drop_column(column_name)
                    print(f"   ✅ Dropped column: {column_name} (SQLite)")
                else:
                    # Fallback for other databases
                    bind.execute(text(f"ALTER TABLE inventory_history DROP COLUMN {column_name}"))
                    print(f"   ✅ Dropped column: {column_name} (Generic)")
            except Exception as e:
                print(f"   ❌ Failed to drop {column_name}: {e}")
                # If direct drop fails, try to at least make it nullable
                try:
                    if db_type == 'postgresql':
                        bind.execute(text(f"ALTER TABLE inventory_history ALTER COLUMN {column_name} DROP NOT NULL"))
                        print(f"   ⚠️  Made {column_name} nullable as fallback")
                    elif db_type == 'sqlite':
                        # SQLite doesn't support ALTER COLUMN, so we'll just continue
                        print(f"   ⚠️  SQLite doesn't support making columns nullable - skipping {column_name}")
                except Exception as e2:
                    print(f"   ❌ Could not even make column nullable: {e2}")
        else:
            print(f"   ℹ️  Column {column_name} does not exist")
    
    # Ensure required columns exist with proper defaults
    required_columns = [
        ('remaining_quantity', 'FLOAT DEFAULT 0.0', 'REAL DEFAULT 0.0'),
        ('fifo_code', 'VARCHAR(50)', 'TEXT'),
        ('expiration_date', 'DATE', 'DATE'),
        ('fifo_reference_id', 'INTEGER', 'INTEGER'),
        ('quantity_used', 'FLOAT DEFAULT 0.0', 'REAL DEFAULT 0.0'),
        ('is_perishable', 'BOOLEAN DEFAULT FALSE', 'INTEGER DEFAULT 0'),
        ('shelf_life_days', 'INTEGER', 'INTEGER'),
        ('created_by', 'INTEGER', 'INTEGER'),
        ('unit_cost', 'FLOAT', 'REAL'),
    ]
    
    for col_name, pg_def, sqlite_def in required_columns:
        if not column_exists('inventory_history', col_name):
            try:
                if db_type == 'postgresql':
                    bind.execute(text(f"ALTER TABLE inventory_history ADD COLUMN {col_name} {pg_def}"))
                elif db_type == 'sqlite':
                    bind.execute(text(f"ALTER TABLE inventory_history ADD COLUMN {col_name} {sqlite_def}"))
                else:
                    # Fallback to PostgreSQL syntax for other databases
                    bind.execute(text(f"ALTER TABLE inventory_history ADD COLUMN {col_name} {pg_def}"))
                print(f"   ✅ Added required column: {col_name}")
            except Exception as e:
                print(f"   ⚠️  Could not add {col_name}: {e}")
    
    print("=== Force drop completed ===")

def downgrade():
    """This is a destructive migration - no downgrade available"""
    print("=== No downgrade available for force drop ===")
    pass
