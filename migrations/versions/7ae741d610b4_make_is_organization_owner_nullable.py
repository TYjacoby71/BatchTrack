"""make_is_organization_owner_nullable

Revision ID: 7ae741d610b4
Revises: zzz_final_merge_all_heads
Create Date: 2025-07-22 23:15:33.918078

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7ae741d610b4'
down_revision = 'zzz_final_merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Make the column nullable and set proper defaults
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Change the column to be nullable with a default of False
        batch_op.alter_column('is_organization_owner', 
                              nullable=True, 
                              server_default='0')  # 0 = False for SQLite
    
    # Update existing NULL values to False
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE user SET is_organization_owner = 0 WHERE is_organization_owner IS NULL")
    )

def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('is_organization_owner', 
                              nullable=False)
