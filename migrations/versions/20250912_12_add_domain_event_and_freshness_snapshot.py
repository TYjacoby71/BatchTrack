"""
Add domain_event and freshness_snapshot tables

Revision ID: 20250912_01
Revises: 20250913014500
Create Date: 2025-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '20250912_01'
down_revision = '20250913014500'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect

    def table_exists(table_name):
        """Check if a table exists"""
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()

    def index_exists(table_name, index_name):
        """Check if an index exists on a table"""
        if not table_exists(table_name):
            return False
        try:
            bind = op.get_bind()
            result = bind.execute(text("""
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE tablename = :table_name
                AND indexname = :index_name
            """), {"table_name": table_name, "index_name": index_name})
            return result.scalar() > 0
        except Exception:
            return False

    def constraint_exists(table_name, constraint_name):
        """Check if a constraint exists on a table"""
        if not table_exists(table_name):
            return False
        try:
            bind = op.get_bind()
            result = bind.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE table_name = :table_name
                AND constraint_name = :constraint_name
            """), {"table_name": table_name, "constraint_name": constraint_name})
            return result.scalar() > 0
        except Exception:
            return False

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
            if not index_exists('domain_event', idx_name):
                try:
                    print(f"   Creating index {idx_name}...")
                    op.create_index(idx_name, 'domain_event', columns)
                    print(f"   ✅ Created index {idx_name}")
                except Exception as e:
                    print(f"   ⚠️  Could not create index {idx_name}: {e}")
            else:
                print(f"   ✅ Index {idx_name} already exists - skipping")

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
            if not index_exists('freshness_snapshot', idx_name):
                try:
                    print(f"   Creating index {idx_name}...")
                    op.create_index(idx_name, 'freshness_snapshot', columns)
                    print(f"   ✅ Created index {idx_name}")
                except Exception as e:
                    print(f"   ⚠️  Could not create index {idx_name}: {e}")
            else:
                print(f"   ✅ Index {idx_name} already exists - skipping")

        # 9. Create unique constraint for freshness_snapshot
        print("   Checking for unique constraint uq_freshness_snapshot_unique...")
        if not constraint_exists('freshness_snapshot', 'uq_freshness_snapshot_unique'):
            try:
                print("   Creating unique constraint uq_freshness_snapshot_unique...")
                op.create_unique_constraint('uq_freshness_snapshot_unique', 'freshness_snapshot', ['snapshot_date', 'organization_id', 'inventory_item_id'])
                print("   ✅ Created unique constraint")
            except Exception as e:
                print(f"   ⚠️  Could not create unique constraint: {e}")
        else:
            print("   ✅ Unique constraint already exists")

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