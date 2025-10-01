"""add addon models and tier allowed addons

Revision ID: 20251001_1
Revises: 20250930_5
Create Date: 2025-10-01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251001_1'
down_revision = '20250930_5'
branch_labels = None
depends_on = None


def upgrade():
    # Create addon table
    op.create_table(
        'addon',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('permission_name', sa.String(length=128), nullable=True),
        sa.Column('billing_type', sa.String(length=32), nullable=False, server_default='subscription'),
        sa.Column('stripe_lookup_key', sa.String(length=128), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('key', name='uq_addon_key')
    )

    # Create organization_addon table
    op.create_table(
        'organization_addon',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('addon_id', sa.Integer(), sa.ForeignKey('addon.id'), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('source', sa.String(length=32), nullable=False, server_default='subscription_item'),
        sa.Column('stripe_item_id', sa.String(length=128), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Index('ix_organization_addon_org', 'organization_id'),
        sa.Index('ix_organization_addon_addon', 'addon_id')
    )

    # Create join table for tier allowed addons
    op.create_table(
        'tier_allowed_addon',
        sa.Column('tier_id', sa.Integer(), sa.ForeignKey('subscription_tier.id'), primary_key=True),
        sa.Column('addon_id', sa.Integer(), sa.ForeignKey('addon.id'), primary_key=True)
    )


def downgrade():
    op.drop_table('tier_allowed_addon')
    op.drop_table('organization_addon')
    op.drop_table('addon')

