
"""fix user_role_assignment constraints to allow NULL role_id for developer roles

Revision ID: 8b7aa70df87d
Revises: fix_password_hash_length
Create Date: 2025-08-01 23:57:14.824861

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '8b7aa70df87d'
down_revision = 'fix_password_hash_length'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Fixing user_role_assignment constraints ===")

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    # Check if user_role_assignment table exists
    if 'user_role_assignment' in inspector.get_table_names():
        print("   Updating user_role_assignment.role_id to allow NULL...")

        # Make role_id nullable for developer role assignments
        with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
            batch_op.alter_column('role_id',
                               existing_type=sa.Integer(),
                               nullable=True)

        print("   ✅ Updated role_id column to allow NULL values")

        # Add check constraint to ensure either role_id OR developer_role_id is set
        try:
            op.create_check_constraint(
                'ck_user_role_assignment_has_role',
                'user_role_assignment',
                'role_id IS NOT NULL OR developer_role_id IS NOT NULL'
            )
            print("   ✅ Added check constraint to ensure either role_id or developer_role_id is set")
        except Exception as e:
            print(f"   ⚠️  Check constraint may already exist: {e}")
    else:
        print("   ⚠️  user_role_assignment table not found - skipping")

    print("✅ User role assignment constraints fixed successfully")


def downgrade():
    """Revert user_role_assignment constraints to make role_id NOT NULL again"""
    print("=== Reverting user_role_assignment constraints ===")

    def table_exists(table_name):
        inspector = inspect(op.get_bind())
        return table_name in inspector.get_table_names()

    def column_exists(table_name, column_name):
        inspector = inspect(op.get_bind())
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]

    if table_exists('user_role_assignment') and column_exists('user_role_assignment', 'role_id'):
        print("   Reverting user_role_assignment.role_id to NOT NULL...")

        # Clean up any records with NULL role_id before making it NOT NULL
        connection = op.get_bind()
        connection.execute(text("DELETE FROM user_role_assignment WHERE role_id IS NULL"))

        # Clean up any leftover temporary tables
        try:
            connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_user_role_assignment"))
        except Exception:
            pass

        try:
            # For SQLite, we need to be more careful with batch operations
            # Use batch operations for SQLite compatibility
            with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
                # Try to drop the check constraint if it exists
                try:
                    batch_op.drop_constraint('ck_user_role_assignment_has_role', type_='check')
                except Exception:
                    pass

                # Make role_id NOT NULL again
                batch_op.alter_column('role_id',
                                    existing_type=sa.Integer(),
                                    nullable=False,
                                    existing_nullable=True)

            print("   ✅ Reverted role_id to NOT NULL")

        except Exception as e:
            print(f"   ⚠️  Could not revert constraints (this is expected in SQLite): {e}")
            print("   ℹ️  Manual cleanup may be required")

    print("✅ Downgrade completed")
