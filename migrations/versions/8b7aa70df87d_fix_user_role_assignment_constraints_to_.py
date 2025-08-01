"""fix user_role_assignment constraints to allow NULL role_id for developer roles

Revision ID: 8b7aa70df87d
Revises: fix_password_hash_length
Create Date: 2025-08-01 23:57:14.824861

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b7aa70df87d'
down_revision = 'fix_password_hash_length'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
