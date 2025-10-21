"""
Add domain_event and freshness_snapshot tables

Revision ID: 20250912_01
Revises: 20250913014500
Create Date: 2025-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import (
    table_exists,
    index_exists,
    ensure_unique_constraint_or_index,
    safe_create_index,
)


# revision identifiers, used by Alembic.
revision = '20250912_01'
down_revision = '20250913014500'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect

    print("=== Creating domain_event and freshness_snapshot tables ===")

    # domain_event table
    if not table_exists('domain_event'):
        print("   Creating domain_event table...")
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
        print("   ✅ domain_event table created")
    else:
        print("   ✅ domain_event table already exists - skipping")

    # Indexes for domain_event
    if table_exists('domain_event'):
        domain_event_indexes = [
            ('ix_domain_event_event_name', ['event_name']),
            ('ix_domain_event_occurred_at', ['occurred_at']),
            ('ix_domain_event_org', ['organization_id']),
            ('ix_domain_event_user', ['user_id']),
            ('ix_domain_event_entity', ['entity_type', 'entity_id']),
            ('ix_domain_event_is_processed', ['is_processed']),
            ('ix_domain_event_correlation_id', ['correlation_id']),
        ]

        for idx_name, columns in domain_event_indexes:
            # Idempotent cross-dialect index creation
            created = safe_create_index(idx_name, 'domain_event', columns)
            if not created:
                print(f"   ✅ Index {idx_name} already exists or was skipped")

    # freshness_snapshot table
    if not table_exists('freshness_snapshot'):
        print("   Creating freshness_snapshot table...")
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
        print("   ✅ freshness_snapshot table created")
    else:
        print("   ✅ freshness_snapshot table already exists - skipping")

    # Indexes and unique constraint for freshness_snapshot
    if table_exists('freshness_snapshot'):
        freshness_indexes = [
            ('ix_freshness_snapshot_date', ['snapshot_date']),
            ('ix_freshness_snapshot_org', ['organization_id']),
            ('ix_freshness_snapshot_item', ['inventory_item_id']),
        ]

        for idx_name, columns in freshness_indexes:
            created = safe_create_index(idx_name, 'freshness_snapshot', columns)
            if not created:
                print(f"   ✅ Index {idx_name} already exists or was skipped")

        # 9. Create unique constraint for freshness_snapshot
        print("   Ensuring unique snapshot constraint/index...")
        ensure_unique_constraint_or_index(
            'freshness_snapshot',
            'uq_freshness_snapshot_unique',
            ['snapshot_date', 'organization_id', 'inventory_item_id'],
        )

    print("✅ Domain event and freshness snapshot migration completed")


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