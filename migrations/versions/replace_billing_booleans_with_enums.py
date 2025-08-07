
"""replace billing provider booleans with enum fields

Revision ID: b5c7d8e9f1a2
Revises: 9a2b8c4d5e6f
Create Date: 2025-08-06 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5c7d8e9f1a2'
down_revision = '9a2b8c4d5e6f'
branch_labels = None
depends_on = None


def upgrade():
    """Replace billing provider booleans with enum fields"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Replacing billing provider booleans with enum fields ===")

    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Add new fields
        if not column_exists('subscription_tier', 'tier_type'):
            print("   Adding tier_type column...")
            batch_op.add_column(sa.Column('tier_type', sa.String(32), default='paid'))
        
        if not column_exists('subscription_tier', 'billing_provider'):
            print("   Adding billing_provider column...")
            batch_op.add_column(sa.Column('billing_provider', sa.String(32), nullable=True))

    # Migrate existing data
    print("   Migrating existing data...")
    connection.execute(sa.text("""
        UPDATE subscription_tier 
        SET tier_type = 'exempt' 
        WHERE key = 'exempt'
    """))
    
    connection.execute(sa.text("""
        UPDATE subscription_tier 
        SET tier_type = 'paid', billing_provider = 'stripe' 
        WHERE requires_stripe_billing = true
    """))
    
    connection.execute(sa.text("""
        UPDATE subscription_tier 
        SET tier_type = 'paid', billing_provider = 'whop' 
        WHERE requires_whop_billing = true AND requires_stripe_billing = false
    """))

    # Drop old columns
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        if column_exists('subscription_tier', 'requires_stripe_billing'):
            print("   Dropping requires_stripe_billing column...")
            batch_op.drop_column('requires_stripe_billing')
        
        if column_exists('subscription_tier', 'requires_whop_billing'):
            print("   Dropping requires_whop_billing column...")
            batch_op.drop_column('requires_whop_billing')

    print("✅ Billing provider migration completed")


def downgrade():
    """Restore billing provider boolean fields"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Restoring billing provider boolean fields ===")

    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Add back old fields
        if not column_exists('subscription_tier', 'requires_stripe_billing'):
            print("   Adding requires_stripe_billing column...")
            batch_op.add_column(sa.Column('requires_stripe_billing', sa.Boolean, default=True))
        
        if not column_exists('subscription_tier', 'requires_whop_billing'):
            print("   Adding requires_whop_billing column...")
            batch_op.add_column(sa.Column('requires_whop_billing', sa.Boolean, default=False))

    # Migrate data back
    print("   Migrating data back...")
    connection.execute(sa.text("""
        UPDATE subscription_tier 
        SET requires_stripe_billing = (billing_provider = 'stripe'),
            requires_whop_billing = (billing_provider = 'whop')
    """))
    
    connection.execute(sa.text("""
        UPDATE subscription_tier 
        SET requires_stripe_billing = false, requires_whop_billing = false
        WHERE tier_type = 'exempt'
    """))

    # Drop new columns
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        if column_exists('subscription_tier', 'tier_type'):
            print("   Dropping tier_type column...")
            batch_op.drop_column('tier_type')
        
        if column_exists('subscription_tier', 'billing_provider'):
            print("   Dropping billing_provider column...")
            batch_op.drop_column('billing_provider')

    print("✅ Billing provider downgrade completed")
