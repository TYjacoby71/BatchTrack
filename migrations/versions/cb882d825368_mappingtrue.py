
"""mappingtrue

Revision ID: cb882d825368
Revises: aba7fa47ef34
Create Date: 2025-05-02 22:05:45.921419

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb882d825368'
down_revision = 'aba7fa47ef34'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('unit', sa.Column('is_mapped', sa.Boolean(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('unit', 'is_mapped')
