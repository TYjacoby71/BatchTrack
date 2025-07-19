
"""remove organization timezone column

Revision ID: remove_org_timezone
Revises: zzz_final_consolidation
Create Date: 2025-01-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_org_timezone'
down_revision = 'zzz_final_consolidation'
branch_labels = None
depends_on = None


def upgrade():
    # Remove timezone column from organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_column('timezone')


def downgrade():
    # Add timezone column back to organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(64), default='America/New_York'))
