"""Create unified inventory history and merge data

Revision ID: 6f9bc65166b3
Revises: add_email_verified_at_column
Create Date: 2025-08-13 19:25:08.055765

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f9bc65166b3'
down_revision = 'add_email_verified_at_column'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
