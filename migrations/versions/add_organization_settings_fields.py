
"""Add organization settings fields

Revision ID: add_organization_settings
Revises: 
Create Date: 2025-01-17 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_organization_settings'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns to organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_email', sa.String(256), nullable=True))
        batch_op.add_column(sa.Column('timezone', sa.String(64), nullable=True, default='America/New_York'))
        batch_op.add_column(sa.Column('default_units', sa.String(32), nullable=True, default='imperial'))

def downgrade():
    # Remove the columns
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_column('default_units')
        batch_op.drop_column('timezone')
        batch_op.drop_column('contact_email')
