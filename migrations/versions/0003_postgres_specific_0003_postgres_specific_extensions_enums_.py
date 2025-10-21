"""0003 postgres-specific extensions/enums/indexes

Revision ID: 0003_postgres_specific
Revises: 0002_constraints_indexes_fks
Create Date: 2025-10-21 20:28:45.141626

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_postgres_specific'
down_revision = '0002_constraints_indexes_fks'
branch_labels = None
depends_on = None


def upgrade():
    # Postgres-only extras; safe no-op on SQLite
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Enable commonly used extensions if available
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
        op.execute('CREATE EXTENSION IF NOT EXISTS "citext";')

        # Example: ensure updated_at auto-update via trigger for specific tables
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'set_updated_at'
                ) THEN
                    CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                END IF;
            END $$;
            """
        )

        # Attach trigger to selected tables that have updated_at
        for table in (
            "addon",
            "organization_addon",
            "product_sku",
            "product",
            "unit",
            "user_preferences",
            "subscription_tier",
        ):
            op.execute(
                sa.text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger WHERE tgname = :trg
                        ) THEN
                            EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I\n'
                                'FOR EACH ROW EXECUTE FUNCTION set_updated_at()', :trg, :tbl);
                        END IF;
                    END $$;
                    """
                ).bindparams(tbl=table, trg=f"trg_{table}_updated_at")
            )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Drop triggers if they exist
        for table in (
            "addon",
            "organization_addon",
            "product_sku",
            "product",
            "unit",
            "user_preferences",
            "subscription_tier",
        ):
            op.execute(sa.text('DROP TRIGGER IF EXISTS "trg_' + table + '_updated_at" ON "' + table + '";'))
        # Function can remain shared; safe to drop if desired
        op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")
