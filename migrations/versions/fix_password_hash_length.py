
"""fix password hash column length

Revision ID: fix_password_hash_length
Revises: add_ingredient_category_updated_at
Create Date: 2025-08-01 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_password_hash_length'
down_revision = 'add_ingredient_category_updated_at'
branch_labels = None
depends_on = None


def upgrade():
    """Increase password_hash column length to accommodate longer hashes"""
    print("=== Fixing password_hash column length ===")
    
    # Increase password_hash length from 120 to 255
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
                              existing_type=sa.VARCHAR(length=120),
                              type_=sa.String(length=255),
                              existing_nullable=False)
    
    print("✅ Password hash column length increased to 255")


def downgrade():
    """Revert password_hash column length back to 120"""
    print("=== Reverting password_hash column length ===")
    
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
                              existing_type=sa.VARCHAR(length=255),
                              type_=sa.String(length=120),
                              existing_nullable=False)
    
    print("✅ Password hash column length reverted to 120")
