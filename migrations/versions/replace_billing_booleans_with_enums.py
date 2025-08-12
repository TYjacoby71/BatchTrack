
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

    # 2) Migrate data only if legacy boolean columns still exist
    legacy_cols = {"requires_stripe_billing", "requires_google_billing", "requires_whop_billing"}
    existing_legacy = legacy_cols & cols
    
    if existing_legacy:
        print("   Migrating existing data from legacy boolean columns...")
        try:
            bind.execute(text("""
                UPDATE subscription_tier
                SET
                  tier_type = CASE
                    WHEN COALESCE(requires_stripe_billing, 0) = 1
                      OR COALESCE(requires_google_billing, 0) = 1  
                      OR COALESCE(requires_whop_billing, 0) = 1
                    THEN 'paid' ELSE 'free' END,
                  billing_provider = CASE
                    WHEN COALESCE(requires_stripe_billing, 0) = 1 THEN 'stripe'
                    WHEN COALESCE(requires_google_billing, 0) = 1 THEN 'google'
                    WHEN COALESCE(requires_whop_billing, 0) = 1 THEN 'whop'
                    ELSE NULL END
            """))
            print("   ✅ Data migration completed")
        except Exception as e:
            print(f"   ⚠️  Data migration failed: {e}")
            
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
        print("   Legacy boolean columns not found - setting safe defaults...")
        # Legacy columns already gone; set safe defaults if still NULL
        try:
            bind.execute(text("""
                UPDATE subscription_tier 
                SET 
                  tier_type = COALESCE(tier_type, 'free'),
                  billing_provider = COALESCE(billing_provider, NULL)
                WHERE tier_type IS NULL
            """))
            print("   ✅ Set default values")
        except Exception as e:
            print(f"   ⚠️  Could not set defaults: {e}")

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
    
    # Migrate data back from enum to booleans
    if "billing_provider" in cols:
        try:
            bind.execute(text("""
                UPDATE subscription_tier SET
                  requires_stripe_billing = CASE WHEN billing_provider = 'stripe' THEN 1 ELSE 0 END,
                  requires_google_billing = CASE WHEN billing_provider = 'google' THEN 1 ELSE 0 END,
                  requires_whop_billing = CASE WHEN billing_provider = 'whop' THEN 1 ELSE 0 END
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
