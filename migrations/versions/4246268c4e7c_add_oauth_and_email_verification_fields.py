"""add_oauth_and_email_verification_fields

Revision ID: 4246268c4e7c
Revises: 3f7a8b9c2d5e
Create Date: 2025-08-06 18:34:57.918991

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4246268c4e7c'
down_revision = '3f7a8b9c2d5e'
branch_labels = None
depends_on = None


def upgrade():
    """Add OAuth and email verification fields to user table"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Adding OAuth and email verification fields ===")

    # Only add columns if they don't already exist
    with op.batch_alter_table('developer_permission', schema=None) as batch_op:
        # Check if 'created_at' column exists before adding
        if not column_exists('developer_permission', 'created_at'):
            print("   Adding created_at column to developer_permission...")
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        else:
            print("   ⚠️  created_at column already exists in developer_permission, skipping")


    with op.batch_alter_table('developer_role', schema=None) as batch_op:
        # Check if 'created_at' column exists before adding
        if not column_exists('developer_role', 'created_at'):
            print("   Adding created_at column to developer_role...")
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        else:
            print("   ⚠️  created_at column already exists in developer_role, skipping")

    with op.batch_alter_table('organization', schema=None) as batch_op:
        # The original code alters whop_license_key, we will keep this as is.
        # If a check is needed, it would be more complex as it's an alter_column.
        batch_op.alter_column('whop_license_key',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=255),
               existing_nullable=True)

    with op.batch_alter_table('user', schema=None) as batch_op:
        if not column_exists('user', 'email_verified'):
            print("   Adding email_verified column...")
            batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=True))
        else:
            print("   ⚠️  email_verified column already exists, skipping")

        if not column_exists('user', 'email_verification_token'):
            print("   Adding email_verification_token column...")
            batch_op.add_column(sa.Column('email_verification_token', sa.String(length=255), nullable=True))
        else:
            print("   ⚠️  email_verification_token column already exists, skipping")

        if not column_exists('user', 'email_verification_sent_at'):
            print("   Adding email_verification_sent_at column...")
            batch_op.add_column(sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
        else:
            print("   ⚠️  email_verification_sent_at column already exists, skipping")

        if not column_exists('user', 'oauth_provider'):
            print("   Adding oauth_provider column...")
            batch_op.add_column(sa.Column('oauth_provider', sa.String(length=50), nullable=True))
        else:
            print("   ⚠️  oauth_provider column already exists, skipping")

        if not column_exists('user', 'oauth_provider_id'):
            print("   Adding oauth_provider_id column...")
            batch_op.add_column(sa.Column('oauth_provider_id', sa.String(length=255), nullable=True))
        else:
            print("   ⚠️  oauth_provider_id column already exists, skipping")

        if not column_exists('user', 'password_reset_token'):
            print("   Adding password_reset_token column...")
            batch_op.add_column(sa.Column('password_reset_token', sa.String(length=255), nullable=True))
        else:
            print("   ⚠️  password_reset_token column already exists, skipping")

        if not column_exists('user', 'password_reset_sent_at'):
            print("   Adding password_reset_sent_at column...")
            batch_op.add_column(sa.Column('password_reset_sent_at', sa.DateTime(), nullable=True))
        else:
            print("   ⚠️  password_reset_sent_at column already exists, skipping")

        # Adding google_id as per the provided changes snippet
        if not column_exists('user', 'google_id'):
            print("   Adding google_id column...")
            batch_op.add_column(sa.Column('google_id', sa.String(length=255), nullable=True))
        else:
            print("   ⚠️  google_id column already exists, skipping")

    print("✅ Migration completed: OAuth and email verification fields")


def downgrade():
    """Remove OAuth and email verification fields from user table"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Removing OAuth and email verification fields ===")

    # Only drop columns if they exist
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Dropping columns that were explicitly mentioned in the changes for downgrade
        if column_exists('user', 'password_reset_sent_at'): # Keeping original downgrade logic for these
            print("   Dropping password_reset_sent_at column...")
            batch_op.drop_column('password_reset_sent_at')
        else:
            print("   ⚠️  password_reset_sent_at column doesn't exist, skipping")

        if column_exists('user', 'password_reset_token'): # Keeping original downgrade logic for these
            print("   Dropping password_reset_token column...")
            batch_op.drop_column('password_reset_token')
        else:
            print("   ⚠️  password_reset_token column doesn't exist, skipping")

        if column_exists('user', 'oauth_provider_id'): # Keeping original downgrade logic for these
            print("   Dropping oauth_provider_id column...")
            batch_op.drop_column('oauth_provider_id')
        else:
            print("   ⚠️  oauth_provider_id column doesn't exist, skipping")

        if column_exists('user', 'oauth_provider'): # Keeping original downgrade logic for these
            print("   Dropping oauth_provider column...")
            batch_op.drop_column('oauth_provider')
        else:
            print("   ⚠️  oauth_provider column doesn't exist, skipping")

        if column_exists('user', 'email_verification_sent_at'): # Keeping original downgrade logic for these
            print("   Dropping email_verification_sent_at column...")
            batch_op.drop_column('email_verification_sent_at')
        else:
            print("   ⚠️  email_verification_sent_at column doesn't exist, skipping")

        if column_exists('user', 'email_verification_token'):
            print("   Dropping email_verification_token column...")
            batch_op.drop_column('email_verification_token')
        else:
            print("   ⚠️  email_verification_token column doesn't exist, skipping")

        if column_exists('user', 'email_verified'):
            print("   Dropping email_verified column...")
            batch_op.drop_column('email_verified')
        else:
            print("   ⚠️  email_verified column doesn't exist, skipping")

        if column_exists('user', 'google_id'):
            print("   Dropping google_id column...")
            batch_op.drop_column('google_id')
        else:
            print("   ⚠️  google_id column doesn't exist, skipping")


    with op.batch_alter_table('organization', schema=None) as batch_op:
        # The original code alters whop_license_key, we will keep this as is.
        batch_op.alter_column('whop_license_key',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=128),
               existing_nullable=True)

    with op.batch_alter_table('developer_role', schema=None) as batch_op:
        # Check if 'created_at' column exists before dropping
        if column_exists('developer_role', 'created_at'):
            print("   Dropping created_at column from developer_role...")
            batch_op.drop_column('created_at')
        else:
            print("   ⚠️  created_at column doesn't exist in developer_role, skipping")

    with op.batch_alter_table('developer_permission', schema=None) as batch_op:
        # Check if 'created_at' column exists before dropping
        if column_exists('developer_permission', 'created_at'):
            print("   Dropping created_at column from developer_permission...")
            batch_op.drop_column('created_at')
        else:
            print("   ⚠️  created_at column doesn't exist in developer_permission, skipping")

    print("✅ Downgrade completed: OAuth and email verification fields removed")