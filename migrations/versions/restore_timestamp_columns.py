"""restore timestamp columns

Revision ID: restore_timestamps  
Revises: fix_nullable_constraints
Create Date: 2025-08-01 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect


# revision identifiers, used by Alembic.
revision = 'restore_timestamps'
down_revision = 'fix_nullable_constraints'
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


def upgrade():
    print("=== Restoring and standardizing timestamp columns ===")

    bind = op.get_bind()

    # Tables that should have updated_at but might be missing it
    tables_needing_updated_at = [
        'organization',
        'role', 
        'user',
        'subscription_tier',
        'developer_role',
        'user_role_assignment',
        'permission',
        'developer_permission'
    ]

    for table_name in tables_needing_updated_at:
        if table_exists(table_name):
            if not column_exists(table_name, 'updated_at'):
                print(f"Adding updated_at to {table_name}")
                with op.batch_alter_table(table_name, schema=None) as batch_op:
                    batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

                # Set initial values to created_at if available, or current timestamp
                if column_exists(table_name, 'created_at'):
                    if table_name == 'role' or table_name == 'user':
                        # Quote table names that might be reserved keywords
                        bind.execute(text(f'UPDATE "{table_name}" SET updated_at = created_at WHERE updated_at IS NULL'))
                    else:
                        bind.execute(text(f'UPDATE {table_name} SET updated_at = created_at WHERE updated_at IS NULL'))
                else:
                    # Use current timestamp as fallback
                    if table_name == 'role' or table_name == 'user':
                        # Set initial values for existing records - database agnostic
                        from sqlalchemy import func
                        bind.execute(text(f'UPDATE "{table_name}" SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'))
                    else:
                        # Set initial values for existing records - database agnostic
                        from sqlalchemy import func
                        bind.execute(text(f'UPDATE {table_name} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'))
            else:
                print(f"✅ {table_name}.updated_at already exists")
        else:
            print(f"⚠️  Table {table_name} doesn't exist, skipping")

    print("✅ Timestamp columns restored and standardized")


def downgrade():
    print("=== Removing restored timestamp columns ===")

    tables_to_clean = [
        'developer_permission',
        'permission',
        'user_role_assignment',
        'developer_role',
        'subscription_tier',
        'user',
        'role',
        'organization'
    ]

    for table_name in tables_to_clean:
        if table_exists(table_name) and column_exists(table_name, 'updated_at'):
            print(f"Removing updated_at from {table_name}")
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.drop_column('updated_at')

    print("✅ Timestamp columns removed")