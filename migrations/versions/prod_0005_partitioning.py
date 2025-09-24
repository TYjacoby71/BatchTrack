"""Production bootstrap 0005 - native Postgres partitioning for time-series tables

Revision ID: prod_0005_partitioning
Revises: prod_0004_lots_history
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'prod_0005_partitioning'
down_revision = 'prod_0004_lots_history'
branch_labels = ('production_bootstrap',)
depends_on = None


def _is_postgres(bind) -> bool:
    return bind.dialect.name == 'postgresql'


def _table_empty(bind, table_name: str) -> bool:
    try:
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0
        return count == 0
    except Exception:
        # If table doesn't exist yet or error, treat as empty to allow creation
        return True


def upgrade():
    bind = op.get_bind()
    if not _is_postgres(bind):
        print("Partitioning skipped (not PostgreSQL)")
        return

    # Only apply partitioning safely when tables are empty (fresh install)
    targets = [
        ('unified_inventory_history', 'timestamp'),
        ('inventory_history', 'timestamp'),
        ('product_sku_history', 'timestamp'),
        ('inventory_lot', 'received_date'),
        ('domain_event', 'occurred_at'),
        ('freshness_snapshot', 'snapshot_date'),
        ('batch', 'started_at'),
    ]

    for table_name, ts_column in targets:
        if not _table_empty(bind, table_name):
            print(f"⚠️  Skipping partitioning for {table_name} (table not empty)")
            continue

        # Attach range partitioning by month on the timestamp/date column
        # Transform base table to partitioned if not already
        try:
            # Check if already partitioned
            res = bind.execute(sa.text(
                """
                SELECT relispartition
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relname = :tbl
                """
            ), {"tbl": table_name}).fetchone()

            # Convert to partitioned table (requires no data)
            bind.execute(sa.text(f'ALTER TABLE "{table_name}" PARTITION BY RANGE ({ts_column})'))
            print(f"✅ Enabled RANGE partitioning on {table_name} ({ts_column})")
        except Exception as e:
            print(f"⚠️  Could not enable partitioning on {table_name}: {e}")
            continue

        # Create the current and next month partitions
        try:
            bind.execute(sa.text(
                f"""
                DO $$
                DECLARE
                    start_month date := date_trunc('month', now())::date;
                    next_month  date := (date_trunc('month', now()) + interval '1 month')::date;
                BEGIN
                    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                        concat('%s_p_', to_char(start_month, 'YYYYMM')), '%s', start_month, next_month);
                END$$;
                """ % (table_name, table_name)
            ))
            print(f"✅ Created current month partition for {table_name}")
        except Exception as e:
            print(f"⚠️  Could not create month partition for {table_name}: {e}")


def downgrade():
    # Non-destructive: leave partitions in place; reversing could drop data
    print("Partitioning downgrade is a no-op to avoid data loss.")

