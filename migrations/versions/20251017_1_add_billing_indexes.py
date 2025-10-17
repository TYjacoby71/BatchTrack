"""add billing performance indexes

Revision ID: 20251017_1
Revises: 20251016_2
Create Date: 2025-10-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251017_1'
down_revision = '20251016_2'
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    try:
        inspector = inspect(conn)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    try:
        inspector = inspect(conn)
        for ix in inspector.get_indexes(table_name):
            if ix.get('name') == index_name:
                return True
        return False
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    # Organization indexes
    if _table_exists(conn, 'organization'):
        if not _index_exists(conn, 'organization', 'ix_organization_subscription_tier_id'):
            try:
                op.create_index('ix_organization_subscription_tier_id', 'organization', ['subscription_tier_id'])
            except Exception:
                pass
        if not _index_exists(conn, 'organization', 'ix_organization_billing_status'):
            try:
                op.create_index('ix_organization_billing_status', 'organization', ['billing_status'])
            except Exception:
                pass
        if not _index_exists(conn, 'organization', 'ix_organization_stripe_customer_id'):
            try:
                op.create_index('ix_organization_stripe_customer_id', 'organization', ['stripe_customer_id'])
            except Exception:
                pass

    # Subscription tier indexes
    if _table_exists(conn, 'subscription_tier'):
        if not _index_exists(conn, 'subscription_tier', 'ix_subscription_tier_billing_provider'):
            try:
                op.create_index('ix_subscription_tier_billing_provider', 'subscription_tier', ['billing_provider'])
            except Exception:
                pass
        if not _index_exists(conn, 'subscription_tier', 'ix_subscription_tier_is_customer_facing'):
            try:
                op.create_index('ix_subscription_tier_is_customer_facing', 'subscription_tier', ['is_customer_facing'])
            except Exception:
                pass

    # Stripe event non-unique index for event_type
    if _table_exists(conn, 'stripe_event'):
        if not _index_exists(conn, 'stripe_event', 'ix_stripe_event_event_type'):
            try:
                op.create_index('ix_stripe_event_event_type', 'stripe_event', ['event_type'])
            except Exception:
                pass


def downgrade():
    conn = op.get_bind()
    try:
        if _table_exists(conn, 'organization'):
            for name in [
                'ix_organization_subscription_tier_id',
                'ix_organization_billing_status',
                'ix_organization_stripe_customer_id',
            ]:
                try:
                    op.drop_index(name, table_name='organization')
                except Exception:
                    pass
        if _table_exists(conn, 'subscription_tier'):
            for name in [
                'ix_subscription_tier_billing_provider',
                'ix_subscription_tier_is_customer_facing',
            ]:
                try:
                    op.drop_index(name, table_name='subscription_tier')
                except Exception:
                    pass
        if _table_exists(conn, 'stripe_event'):
            try:
                op.drop_index('ix_stripe_event_event_type', table_name='stripe_event')
            except Exception:
                pass
    except Exception:
        pass
