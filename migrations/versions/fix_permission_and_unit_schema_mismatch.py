
"""fix permission and unit schema mismatch

Revision ID: fix_perm_unit_schema
Revises: edb302e17958
Create Date: 2025-08-25 17:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_perm_unit_schema'
down_revision = 'edb302e17958'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except:
        return False

def upgrade():
    """Fix schema mismatches for permission and unit tables"""
    print("=== Fixing Permission and Unit Schema Mismatches ===")
    
    # Fix permission table - add back is_active column
    if not column_exists('permission', 'is_active'):
        print("   Adding is_active column to permission table...")
        op.add_column('permission', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
        print("   ✅ is_active column added to permission table")
    else:
        print("   ✅ is_active column already exists in permission table")
    
    # Add created_at to permission if missing
    if not column_exists('permission', 'created_at'):
        print("   Adding created_at column to permission table...")
        op.add_column('permission', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
        print("   ✅ created_at column added to permission table")
    else:
        print("   ✅ created_at column already exists in permission table")
    
    # Fix unit table - rename is_base_unit to base_unit and change type
    if column_exists('unit', 'is_base_unit') and not column_exists('unit', 'base_unit'):
        print("   Converting unit.is_base_unit to unit.base_unit...")
        
        # Add new base_unit column
        op.add_column('unit', sa.Column('base_unit', sa.String(64), nullable=True))
        
        # Copy data: if is_base_unit is True, set base_unit to the unit's own name
        connection = op.get_bind()
        connection.execute(sa.text("""
            UPDATE unit 
            SET base_unit = CASE 
                WHEN is_base_unit = true THEN name 
                ELSE NULL 
            END
        """))
        
        # Drop old column
        op.drop_column('unit', 'is_base_unit')
        print("   ✅ Converted is_base_unit to base_unit column")
    elif column_exists('unit', 'base_unit'):
        print("   ✅ base_unit column already exists in unit table")
    else:
        print("   Adding base_unit column to unit table...")
        op.add_column('unit', sa.Column('base_unit', sa.String(64), nullable=True))
        print("   ✅ base_unit column added to unit table")
    
    print("✅ Schema mismatch fixes completed")

def downgrade():
    """Revert schema changes"""
    print("   ⚠️  Downgrade would revert to problematic schema - not implemented")
    pass
