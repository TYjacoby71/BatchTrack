
"""Make organization_id nullable

Revision ID: make_organization_id_nullable
Revises: b2b4ce5f93fd
Create Date: 2025-07-18 01:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'make_organization_id_nullable'
down_revision = 'b2b4ce5f93fd'
branch_labels = None
depends_on = None

def upgrade():
    # Make organization_id nullable in user table using batch operations for SQLite
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Alter the column to be nullable
        batch_op.alter_column('organization_id',
                             existing_type=sa.Integer(),
                             nullable=True)

def downgrade():
    # Make organization_id not nullable again
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('organization_id',
                             existing_type=sa.Integer(),
                             nullable=False)
