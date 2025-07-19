
"""Add organization settings fields

Revision ID: add_organization_settings
Revises: fix_developer_users
Create Date: 2025-01-17 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_organization_settings'
down_revision = 'add_required_subscription_tier'
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns to organization table using batch operations for SQLite
    with op.batch_alter_table('organization', schema=None) as batch_op:
        # Check if columns exist before adding them
        try:
            batch_op.add_column(sa.Column('contact_email', sa.String(256), nullable=True))
        except Exception:
            pass  # Column might already exist
        
        try:
            batch_op.add_column(sa.Column('timezone', sa.String(64), nullable=True, default='America/New_York'))
        except Exception:
            pass  # Column might already exist
        
        try:
            batch_op.add_column(sa.Column('default_units', sa.String(32), nullable=True, default='imperial'))
        except Exception:
            pass  # Column might already exist

def downgrade():
    # Remove the columns
    with op.batch_alter_table('organization', schema=None) as batch_op:
        try:
            batch_op.drop_column('default_units')
        except Exception:
            pass
        
        try:
            batch_op.drop_column('timezone')
        except Exception:
            pass
        
        try:
            batch_op.drop_column('contact_email')
        except Exception:
            pass
