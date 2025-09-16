"""
Add domain_event and freshness_snapshot tables

Revision ID: 20250912_01
Revises: 20250913014500
Create Date: 2025-09-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250912_01'
down_revision = '20250913014500'
branch_labels = None
depends_on = None


def upgrade():
    # domain_event table
    op.create_table(
        'domain_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_name', sa.String(length=128), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('entity_type', sa.String(length=64), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('correlation_id', sa.String(length=128), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True, server_default=sa.text("'app'")),
        sa.Column('schema_version', sa.Integer(), nullable=True, server_default=sa.text('1')),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('delivery_attempts', sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # Indexes for domain_event
    op.create_index('ix_domain_event_event_name', 'domain_event', ['event_name'])
    op.create_index('ix_domain_event_occurred_at', 'domain_event', ['occurred_at'])
    op.create_index('ix_domain_event_org', 'domain_event', ['organization_id'])
    op.create_index('ix_domain_event_user', 'domain_event', ['user_id'])
    op.create_index('ix_domain_event_entity', 'domain_event', ['entity_type', 'entity_id'])
    op.create_index('ix_domain_event_is_processed', 'domain_event', ['is_processed'])
    op.create_index('ix_domain_event_correlation_id', 'domain_event', ['correlation_id'])

    # freshness_snapshot table
    op.create_table(
        'freshness_snapshot',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_item.id'), nullable=False),
        sa.Column('avg_days_to_usage', sa.Float(), nullable=True),
        sa.Column('avg_days_to_spoilage', sa.Float(), nullable=True),
        sa.Column('freshness_efficiency_score', sa.Float(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=True),
    )

    # Indexes and unique constraint for freshness_snapshot
    op.create_index('ix_freshness_snapshot_date', 'freshness_snapshot', ['snapshot_date'])
    op.create_index('ix_freshness_snapshot_org', 'freshness_snapshot', ['organization_id'])
    op.create_index('ix_freshness_snapshot_item', 'freshness_snapshot', ['inventory_item_id'])
    op.create_unique_constraint('uq_freshness_snapshot_unique', 'freshness_snapshot', ['snapshot_date', 'organization_id', 'inventory_item_id'])


def downgrade():
    # Drop freshness_snapshot
    try:
        op.drop_constraint('uq_freshness_snapshot_unique', 'freshness_snapshot', type_='unique')
    except Exception:
        pass
    for idx in ['ix_freshness_snapshot_item', 'ix_freshness_snapshot_org', 'ix_freshness_snapshot_date']:
        try:
            op.drop_index(idx, table_name='freshness_snapshot')
        except Exception:
            pass
    try:
        op.drop_table('freshness_snapshot')
    except Exception:
        pass

    # Drop domain_event
    for idx in ['ix_domain_event_correlation_id', 'ix_domain_event_is_processed', 'ix_domain_event_entity', 'ix_domain_event_user', 'ix_domain_event_org', 'ix_domain_event_occurred_at', 'ix_domain_event_event_name']:
        try:
            op.drop_index(idx, table_name='domain_event')
        except Exception:
            pass
    try:
        op.drop_table('domain_event')
    except Exception:
        pass

