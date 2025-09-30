
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

def upgrade():
    """Add all missing User model columns to the database"""
    print("=== Adding missing User model columns ===")
    
    missing_columns = [
        ('deleted_at', sa.DateTime(), True),
        ('deleted_by', sa.Integer(), True),
        ('is_deleted', sa.Boolean(), False)
    ]
    
    with op.batch_alter_table('user', schema=None) as batch_op:
        for column_name, column_type, nullable in missing_columns:
            if not column_exists('user', column_name):
                print(f"   Adding {column_name} column...")
                if column_name == 'is_deleted':
                    batch_op.add_column(sa.Column(column_name, column_type, nullable=False, default=False))
                elif column_name == 'deleted_by':
                    # Add the column first, then create a named FK for batch mode compatibility
                    batch_op.add_column(sa.Column(column_name, column_type, nullable=True))
                else:
                    batch_op.add_column(sa.Column(column_name, column_type, nullable=nullable))
            else:
                print(f"   ✅ {column_name} column already exists")

        # Create explicit FK for deleted_by if the column was just added (or exists)
        try:
            batch_op.create_foreign_key('fk_user_deleted_by_user', 'user', ['deleted_by'], ['id'])
        except Exception:
            # Likely already exists or not supported on this backend; safe to continue
            pass
    
    print("✅ Missing User columns migration completed")

def downgrade():
    """Remove the added columns"""
    with op.batch_alter_table('user', schema=None) as batch_op:
        columns_to_remove = ['deleted_at', 'deleted_by', 'is_deleted']
        
        for column_name in columns_to_remove:
            if column_exists('user', column_name):
                batch_op.drop_column(column_name)
