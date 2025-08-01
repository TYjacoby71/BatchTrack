"""merge timestamp and unit_type migrations

Revision ID: 05fab1341ac5
Revises: be3cf5daaa4f, restore_timestamps
Create Date: 2025-08-01 20:36:35.875920

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05fab1341ac5'
down_revision = ('be3cf5daaa4f', 'restore_timestamps')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
