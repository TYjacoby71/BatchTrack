
"""remove organization timezone

Revision ID: remove_organization_timezone
Revises: fd6ec9059553
Create Date: 2025-07-19 06:03:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_organization_timezone'
down_revision = 'fd6ec9059553'
branch_labels = None
depends_on = None


def upgrade():
    # Check if timezone column exists and remove it
    try:
        with op.batch_alter_table('organization', schema=None) as batch_op:
            batch_op.drop_column('timezone')
    except Exception:
        # Column may not exist, which is fine
        pass


def downgrade():
    # Add timezone column back if needed for rollback
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(64), nullable=True, default='UTC'))
