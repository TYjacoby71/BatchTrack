
"""new_fs_uniquifier_migration

Revision ID: new_fs_uniquifier_migration
Revises: e9ef3d8c7df4
Create Date: 2025-07-19 05:57:55.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'new_fs_uniquifier_migration'
down_revision = 'e9ef3d8c7df4'
branch_labels = None
depends_on = None


def upgrade():
    # This is a mock migration to satisfy cached references
    # No actual schema changes needed
    pass


def downgrade():
    # This is a mock migration to satisfy cached references
    # No actual schema changes needed
    pass
