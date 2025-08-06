
"""fix missing email verification columns

Revision ID: fix_missing_email_verification
Revises: 4246268c4e7c
Create Date: 2025-01-06 20:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_missing_email_verification'
down_revision = '4246268c4e7c'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in the database"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    """Add missing email verification columns safely"""
    print("🔧 Fixing missing email verification columns...")
    
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Add email_verification_sent_at if it doesn't exist
        if not column_exists('user', 'email_verification_sent_at'):
            print("   Adding email_verification_sent_at column...")
            batch_op.add_column(sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
        else:
            print("   ✅ email_verification_sent_at column already exists")
            
        # Add password_reset_sent_at if it doesn't exist
        if not column_exists('user', 'password_reset_sent_at'):
            print("   Adding password_reset_sent_at column...")
            batch_op.add_column(sa.Column('password_reset_sent_at', sa.DateTime(), nullable=True))
        else:
            print("   ✅ password_reset_sent_at column already exists")

    print("✅ Email verification columns fix completed")

def downgrade():
    """Remove the added columns"""
    with op.batch_alter_table('user', schema=None) as batch_op:
        if column_exists('user', 'email_verification_sent_at'):
            batch_op.drop_column('email_verification_sent_at')
        if column_exists('user', 'password_reset_sent_at'):
            batch_op.drop_column('password_reset_sent_at')
