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
    inspector = sa.inspect(conn)
    constraints = inspector.get_unique_constraints(table_name) + inspector.get_foreign_keys(table_name)
    return constraint_name in [c['name'] for c in constraints]

def upgrade():
    """Add missing User model columns with soft delete support"""
    print("=== Adding missing User model columns ===")

    # Add columns with proper defaults for existing data
    if not column_exists('user', 'deleted_at'):
        op.add_column('user', sa.Column('deleted_at', sa.DateTime(), nullable=True))
        print("   ✅ Added deleted_at column")
    else:
        print("   ✅ deleted_at column already exists")

    if not column_exists('user', 'deleted_by'):
        op.add_column('user', sa.Column('deleted_by', sa.Integer(), nullable=True))
        print("   ✅ Added deleted_by column")
    else:
        print("   ✅ deleted_by column already exists")

    if not column_exists('user', 'is_deleted'):
        # Add column as nullable first with default False
        op.add_column('user', sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.text('0')))
        print("   ✅ Added is_deleted column")

        # Update all existing records to False
        try:
            op.execute("UPDATE \"user\" SET is_deleted = 0 WHERE is_deleted IS NULL")
        except Exception:
            # Fallback for backends that accept TRUE/FALSE
            op.execute("UPDATE \"user\" SET is_deleted = FALSE WHERE is_deleted IS NULL")

        # Avoid ALTER COLUMN on SQLite; server_default keeps future inserts false
        try:
            op.alter_column('user', 'is_deleted', nullable=False, server_default=sa.text('0'))
            print("   ✅ Set is_deleted NOT NULL with default")
        except Exception as e:
            print(f"   ⚠️  Skipping NOT NULL alter for is_deleted on this dialect: {e}")
    else:
        print("   ✅ is_deleted column already exists")

    # Add foreign key constraint only if it doesn't exist and deleted_by column exists
    if column_exists('user', 'deleted_by'):
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
    with op.batch_alter_table('user', schema=None) as batch_op:
        columns_to_remove = ['deleted_at', 'deleted_by', 'is_deleted']

        for column_name in columns_to_remove:
            if column_exists('user', column_name):
                batch_op.drop_column(column_name)