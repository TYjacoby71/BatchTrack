
"""add missing user columns

Revision ID: add_missing_user_columns
Revises: add_missing_last_login_column
Create Date: 2025-08-25 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_missing_user_columns'
down_revision = 'add_missing_last_login_column'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in the database"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists in the database"""
    conn = op.get_bind()
    try:
        # For PostgreSQL, check pg_constraint
        result = conn.execute(sa.text("""
            SELECT COUNT(*) FROM pg_constraint 
            WHERE conname = :constraint_name
        """), {"constraint_name": constraint_name})
        return result.scalar() > 0
    except:
        # Fallback - assume it doesn't exist
        return False

def upgrade():
    """Add missing User model columns with soft delete support"""
    print("=== Adding missing User model columns ===")
    
    # Check and add columns if they don't exist
    columns_to_add = [
        ('deleted_at', sa.DateTime(), True),
        ('deleted_by', sa.Integer(), True),
        ('is_deleted', sa.Boolean(), False, False)
    ]
    
    for col_name, col_type, nullable, *default in columns_to_add:
        if column_exists('user', col_name):
            print(f"   ✅ {col_name} column already exists")
        else:
            if default:
                op.add_column('user', sa.Column(col_name, col_type, nullable=nullable, default=default[0]))
            else:
                op.add_column('user', sa.Column(col_name, col_type, nullable=nullable))
            print(f"   ✅ Added {col_name} column")
    
    # Add foreign key constraint only if it doesn't exist
    fk_constraint_name = 'fk_user_deleted_by_user'
    if not constraint_exists('user', fk_constraint_name):
        try:
            op.create_foreign_key(
                fk_constraint_name,
                'user', 'user',
                ['deleted_by'], ['id']
            )
            print("   ✅ Added foreign key constraint for deleted_by")
        except Exception as e:
            print(f"   ⚠️  Could not add foreign key constraint: {e}")
    else:
        print("   ✅ Foreign key constraint already exists")

    print("✅ User columns migration completed")

def downgrade():
    """Remove the added columns"""
    try:
        # Remove foreign key constraint first
        op.drop_constraint('fk_user_deleted_by_user', 'user', type_='foreignkey')
    except:
        pass
    
    # Remove columns
    columns_to_remove = ['deleted_at', 'deleted_by', 'is_deleted']
    for col_name in columns_to_remove:
        try:
            op.drop_column('user', col_name)
        except:
            pass
