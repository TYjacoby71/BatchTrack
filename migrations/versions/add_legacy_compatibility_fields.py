 """add legacy compatibility fields to subscription tier

 Revision ID: add_legacy_compatibility_fields
 Revises: add_tier_key_column
 Create Date: 2025-08-11 23:30:00.000000

 """
 from alembic import op
 import sqlalchemy as sa
 from sqlalchemy import inspect

 # revision identifiers, used by Alembic.
 revision = 'add_legacy_compatibility_fields'
 down_revision = 'add_tier_key_column'
 branch_labels = None
 depends_on = None

 def upgrade():
     """Add legacy compatibility fields to subscription_tier table"""

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

     print("=== Adding legacy compatibility fields to subscription_tier ===")

     # Add stripe_product_id column if it doesn't exist
     if not column_exists('subscription_tier', 'stripe_product_id'):
         print("   Adding stripe_product_id column...")
         with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
             batch_op.add_column(sa.Column('stripe_product_id', sa.String(128), nullable=True))
         print("✅ stripe_product_id column added successfully")
     else:
         print("   ⚠️  stripe_product_id column already exists, skipping")

     # Add stripe_price_id column if it doesn't exist
     if not column_exists('subscription_tier', 'stripe_price_id'):
         print("   Adding stripe_price_id column...")
         with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
             batch_op.add_column(sa.Column('stripe_price_id', sa.String(128), nullable=True))
         print("✅ stripe_price_id column added successfully")
     else:
         print("   ⚠️  stripe_price_id column already exists, skipping")

     # Add stripe_price_id_monthly column if it doesn't exist  
     if not column_exists('subscription_tier', 'stripe_price_id_monthly'):
         print("   Adding stripe_price_id_monthly column...")
         with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
             batch_op.add_column(sa.Column('stripe_price_id_monthly', sa.String(128), nullable=True))
         print("✅ stripe_price_id_monthly column added successfully")
     else:
         print("   ⚠️  stripe_price_id_monthly column already exists, skipping")

     # Add stripe_price_id_yearly column if it doesn't exist
     if not column_exists('subscription_tier', 'stripe_price_id_yearly'):
         print("   Adding stripe_price_id_yearly column...")
         with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
             batch_op.add_column(sa.Column('stripe_price_id_yearly', sa.String(128), nullable=True))
         print("✅ stripe_price_id_yearly column added successfully")
     else:
         print("   ⚠️  stripe_price_id_yearly column already exists, skipping")

     print("=== Legacy compatibility fields migration completed ===")

 def downgrade():
     """Remove the legacy compatibility fields"""
     print("=== Removing legacy compatibility fields ===")

     with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
         # Drop columns
         try:
             batch_op.drop_column('stripe_price_id_yearly')
             batch_op.drop_column('stripe_price_id_monthly')
             batch_op.drop_column('stripe_price_id')
             batch_op.drop_column('stripe_product_id')
         except Exception as e:
             print(f"   ⚠️  Could not remove some columns: {e}")

     print("✅ Downgrade completed")
