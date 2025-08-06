
"""fix missing oauth columns postgresql

Revision ID: fix_missing_oauth_columns_postgresql
Revises: 4246268c4e7c
Create Date: 2025-08-06 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_missing_oauth_columns_postgresql'
down_revision = '4246268c4e7c'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing OAuth columns specifically for PostgreSQL"""
    from sqlalchemy import inspect, text

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists_pg(table_name, column_name):
        """Check if a column exists in a PostgreSQL table"""
        try:
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = :table_name 
                AND column_name = :column_name
                AND table_schema = 'public'
            """), {'table_name': table_name, 'column_name': column_name})
            return result.fetchone() is not None
        except Exception as e:
            print(f"Error checking column {column_name}: {e}")
            return False

    print("=== PostgreSQL OAuth Column Fix ===")

    # Add missing OAuth and related columns to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        
        if not column_exists_pg('user', 'oauth_provider'):
            print("   Adding oauth_provider column...")
            batch_op.add_column(sa.Column('oauth_provider', sa.String(length=50), nullable=True))
        else:
            print("   ⚠️  oauth_provider column already exists, skipping")

        if not column_exists_pg('user', 'oauth_provider_id'):
            print("   Adding oauth_provider_id column...")
            batch_op.add_column(sa.Column('oauth_provider_id', sa.String(length=255), nullable=True))
        else:
            print("   ⚠️  oauth_provider_id column already exists, skipping")

        if not column_exists_pg('user', 'password_reset_token'):
            print("   Adding password_reset_token column...")
            batch_op.add_column(sa.Column('password_reset_token', sa.String(length=255), nullable=True))
        else:
            print("   ⚠️  password_reset_token column already exists, skipping")

        if not column_exists_pg('user', 'password_reset_sent_at'):
            print("   Adding password_reset_sent_at column...")
            batch_op.add_column(sa.Column('password_reset_sent_at', sa.DateTime(), nullable=True))
        else:
            print("   ⚠️  password_reset_sent_at column already exists, skipping")

        if not column_exists_pg('user', 'email_verification_sent_at'):
            print("   Adding email_verification_sent_at column...")
            batch_op.add_column(sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
        else:
            print("   ⚠️  email_verification_sent_at column already exists, skipping")

    print("✅ PostgreSQL OAuth columns migration completed")


def downgrade():
    """Remove OAuth columns"""
    print("=== PostgreSQL OAuth Column Removal ===")

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('password_reset_sent_at')
        batch_op.drop_column('password_reset_token')
        batch_op.drop_column('oauth_provider_id')
        batch_op.drop_column('oauth_provider')
        batch_op.drop_column('email_verification_sent_at')

    print("✅ PostgreSQL OAuth columns removal completed")
