
"""add_fs_uniquifier_make_password_nullable

Revision ID: db37ade7bae5
Revises: 28f3476c0a52
Create Date: 2025-07-22 02:24:05.365813

"""
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision = 'db37ade7bae5'
down_revision = '28f3476c0a52'
branch_labels = None
depends_on = None


def upgrade():
    # Get the bind to execute raw SQL
    bind = op.get_bind()
    
    # First, add nullable columns
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Add fs_uniquifier as nullable first
        batch_op.add_column(sa.Column('fs_uniquifier', sa.String(length=255), nullable=True))
    
    # Generate unique fs_uniquifier for existing users
    result = bind.execute(sa.text("SELECT id FROM user WHERE fs_uniquifier IS NULL"))
    for row in result:
        unique_id = str(uuid.uuid4())
        bind.execute(sa.text("UPDATE user SET fs_uniquifier = :unique_id WHERE id = :user_id"), 
                    {"unique_id": unique_id, "user_id": row[0]})
    
    # Now make fs_uniquifier NOT NULL and add unique constraint
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('fs_uniquifier', nullable=False)
        batch_op.create_unique_constraint('uq_user_fs_uniquifier', ['fs_uniquifier'])
        
        # Make password nullable (it should already be nullable based on the model)
        batch_op.alter_column('password', nullable=True)


def downgrade():
    # Remove fs_uniquifier and revert password to NOT NULL
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_fs_uniquifier', type_='unique')
        batch_op.drop_column('fs_uniquifier')
        batch_op.alter_column('password', nullable=False)
