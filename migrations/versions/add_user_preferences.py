
"""Add user preferences table

Revision ID: add_user_preferences
Revises: aa271449bf33
Create Date: 2025-01-10 19:44:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_preferences'
down_revision = 'aa271449bf33'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_preferences table
    op.create_table('user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('max_dashboard_alerts', sa.Integer(), nullable=True),
        sa.Column('show_expiration_alerts', sa.Boolean(), nullable=True),
        sa.Column('show_timer_alerts', sa.Boolean(), nullable=True),
        sa.Column('show_low_stock_alerts', sa.Boolean(), nullable=True),
        sa.Column('show_batch_alerts', sa.Boolean(), nullable=True),
        sa.Column('show_fault_alerts', sa.Boolean(), nullable=True),
        sa.Column('expiration_warning_days', sa.Integer(), nullable=True),
        sa.Column('show_alert_badges', sa.Boolean(), nullable=True),
        sa.Column('dashboard_layout', sa.String(length=32), nullable=True),
        sa.Column('compact_view', sa.Boolean(), nullable=True),
        sa.Column('show_quick_actions', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade():
    op.drop_table('user_preferences')
