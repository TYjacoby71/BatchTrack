"""merge all migration heads

Revision ID: 9a25cdbe385b
Revises: 32aaf310779c, 47eadd04f263, 7fbece7d5bfd, a9764225f9aa, f6a9b50d9a17, final_head_merge_2025, fix_developer_users, remove_default_units, rename_multiplier_cf
Create Date: 2025-07-19 04:49:07.812726

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a25cdbe385b'
down_revision = ('32aaf310779c', '47eadd04f263', '7fbece7d5bfd', 'a9764225f9aa', 'f6a9b50d9a17', 'final_head_merge_2025', 'fix_developer_users', 'remove_default_units', 'rename_multiplier_cf')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
