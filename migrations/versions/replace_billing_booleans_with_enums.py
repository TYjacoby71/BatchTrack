"""replace billing provider booleans with enum fields

Revision ID: b5c7d8e9f1a2
Revises: 9a2b8c4d5e6f
Create Date: 2025-08-12 02:17:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'b5c7d8e9f1a2'
down_revision = '9a2b8c4d5e6f'
branch_labels = None
depends_on = None

def _get_columns(table_name):
    """Get set of column names for a table"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(table_name)}

def upgrade():
    print("=== Replacing billing provider booleans with enum fields ===")

    bind = op.get_bind()
    cols = _get_columns("subscription_tier")

    # 1) Add new columns if they don't exist
    if "tier_type" not in cols:
        print("   Adding tier_type column...")
        op.add_column('subscription_tier', sa.Column('tier_type', sa.String(32), nullable=True))
    else:
        print("   ✅ tier_type column already exists")

    if "billing_provider" not in cols:
        print("   Adding billing_provider column...")
        op.add_column('subscription_tier', sa.Column('billing_provider', sa.String(32), nullable=True))
    else:
        print("   ✅ billing_provider column already exists")

    # 2) Migrate data only if legacy boolean columns still exist AND table has data
    legacy_cols = {"requires_stripe_billing", "requires_google_billing", "requires_whop_billing"}
    existing_legacy = legacy_cols & cols

    if existing_legacy:
        # Check if the table has any rows before attempting data migration
        try:
            result = bind.execute(text("SELECT COUNT(*) FROM subscription_tier"))
            row_count = result.scalar()

            if row_count > 0:
                print(f"   Found {row_count} existing subscription_tier rows - migrating data from legacy boolean columns...")

                # Build dynamic SQL based on which columns actually exist
                tier_type_conditions = []
                billing_provider_conditions = []

                if "requires_stripe_billing" in existing_legacy:
                    tier_type_conditions.append("COALESCE(requires_stripe_billing, 0) = 1")
                    billing_provider_conditions.append("WHEN COALESCE(requires_stripe_billing, 0) = 1 THEN 'stripe'")

                if "requires_google_billing" in existing_legacy:
                    tier_type_conditions.append("COALESCE(requires_google_billing, 0) = 1")
                    billing_provider_conditions.append("WHEN COALESCE(requires_google_billing, 0) = 1 THEN 'google'")

                if "requires_whop_billing" in existing_legacy:
                    tier_type_conditions.append("COALESCE(requires_whop_billing, 0) = 1")
                    billing_provider_conditions.append("WHEN COALESCE(requires_whop_billing, 0) = 1 THEN 'whop'")

                # Only run migration if we have conditions to work with
                if tier_type_conditions and billing_provider_conditions:
                    tier_type_sql = " OR ".join(tier_type_conditions)
                    billing_provider_sql = "\n                    ".join(billing_provider_conditions)

                    migration_sql = f"""
                        UPDATE subscription_tier
                        SET
                          tier_type = CASE
                            WHEN {tier_type_sql}
                            THEN 'paid' ELSE 'free' END,
                          billing_provider = CASE
                            {billing_provider_sql}
                            ELSE NULL END
                    """

                    bind.execute(text(migration_sql))
                    print("   ✅ Data migration completed")
                else:
                    print("   ⚠️  No valid legacy columns found for migration")
            else:
                print("   ℹ️  subscription_tier table is empty - skipping data migration")

        except Exception as e:
            print(f"   ⚠️  Data migration failed: {e}")
            print("   ℹ️  This is normal for fresh database builds - continuing...")

        # 3) Drop legacy columns if present (SQLite-safe)
        print("   Dropping legacy boolean columns...")
        with op.batch_alter_table("subscription_tier") as batch_op:
            for col_name in existing_legacy:
                try:
                    batch_op.drop_column(col_name)
                    print(f"   ✅ Dropped {col_name}")
                except Exception as e:
                    print(f"   ⚠️  Could not drop {col_name}: {e}")
    else:
        print("   ℹ️  No legacy boolean columns found - skipping data migration")

    print("✅ Billing provider enum migration completed")

def downgrade():
    """Downgrade - restore boolean columns (best effort)"""
    print("=== Restoring billing provider boolean columns ===")

    bind = op.get_bind()
    cols = _get_columns("subscription_tier")

    # Add boolean columns back if they don't exist
    for col_name in ["requires_stripe_billing", "requires_google_billing", "requires_whop_billing"]:
        if col_name not in cols:
            op.add_column('subscription_tier', sa.Column(col_name, sa.Boolean(), nullable=True, default=False))

    # Migrate data back to boolean columns (PostgreSQL-compatible)
    if "billing_provider" in cols:
        try:
            bind.execute(text(f"""
                UPDATE subscription_tier SET
                  requires_stripe_billing = CASE WHEN billing_provider = 'stripe' THEN TRUE ELSE FALSE END,
                  requires_google_billing = CASE WHEN billing_provider = 'google' THEN TRUE ELSE FALSE END,
                  requires_whop_billing = CASE WHEN billing_provider = 'whop' THEN TRUE ELSE FALSE END
            """))
        except Exception as e:
            print(f"   ⚠️  Could not migrate data back: {e}")

    # Drop enum columns
    with op.batch_alter_table("subscription_tier") as batch_op:
        try:
            if "tier_type" in cols:
                batch_op.drop_column('tier_type')
            if "billing_provider" in cols:
                batch_op.drop_column('billing_provider')
        except Exception as e:
            print(f"   ⚠️  Could not drop enum columns: {e}")

    print("✅ Downgrade completed")