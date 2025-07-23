
"""Ensure is_organization_owner column exists

Revision ID: 003_ensure_is_organization_owner_column
Revises: 002_add_is_organization_owner_nullable
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_ensure_is_organization_owner_column'
down_revision = '002_add_is_organization_owner_nullable'
branch_labels = None
depends_on = None

def upgrade():
    # Check if column exists before adding it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    if 'is_organization_owner' not in columns:
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_organization_owner', sa.Boolean(), nullable=True, default=False))

def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_organization_owner')
