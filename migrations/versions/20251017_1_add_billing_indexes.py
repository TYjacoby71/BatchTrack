
"""add billing performance indexes

Revision ID: 20251017_1
Revises: 20251016_2
Create Date: 2025-10-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

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


def _safe_create_index(conn, index_name: str, table_name: str, columns: list):
    """Safely create index using raw SQL to avoid transaction issues"""
    if not _table_exists(conn, table_name):
        return False
    
    if _index_exists(conn, table_name, index_name):
        return False
    
    try:
        # Use CREATE INDEX IF NOT EXISTS for PostgreSQL safety
        columns_str = ', '.join(columns)
        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
        conn.execute(text(sql))
        conn.commit()
        return True
    except Exception as e:
        print(f"Warning: Could not create index {index_name}: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False


def upgrade():
    conn = op.get_bind()

    # Organization indexes
    indexes_to_create = [
        ('ix_organization_subscription_tier_id', 'organization', ['subscription_tier_id']),
        ('ix_organization_billing_status', 'organization', ['billing_status']),
        ('ix_organization_stripe_customer_id', 'organization', ['stripe_customer_id']),
        ('ix_subscription_tier_billing_provider', 'subscription_tier', ['billing_provider']),
        ('ix_subscription_tier_is_customer_facing', 'subscription_tier', ['is_customer_facing']),
        ('ix_stripe_event_event_type', 'stripe_event', ['event_type']),
    ]

    for index_name, table_name, columns in indexes_to_create:
        _safe_create_index(conn, index_name, table_name, columns)


def downgrade():
    conn = op.get_bind()
    
    indexes_to_drop = [
        ('ix_organization_subscription_tier_id', 'organization'),
        ('ix_organization_billing_status', 'organization'),
        ('ix_organization_stripe_customer_id', 'organization'),
        ('ix_subscription_tier_billing_provider', 'subscription_tier'),
        ('ix_subscription_tier_is_customer_facing', 'subscription_tier'),
        ('ix_stripe_event_event_type', 'stripe_event'),
    ]
    
    for index_name, table_name in indexes_to_drop:
        if _table_exists(conn, table_name) and _index_exists(conn, table_name, index_name):
            try:
                sql = f"DROP INDEX IF EXISTS {index_name}"
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                print(f"Warning: Could not drop index {index_name}: {e}")
                try:
                    conn.rollback()
                except:
                    pass
