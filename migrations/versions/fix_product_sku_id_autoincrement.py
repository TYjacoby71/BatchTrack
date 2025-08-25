
"""fix product sku id autoincrement

Revision ID: fix_product_sku_id_autoincrement
Revises: simplify_tiers_add_tier_type
Create Date: 2025-08-21 01:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_product_sku_id_autoincrement'
down_revision = 'simplify_tiers_add_tier_type'
branch_labels = None
depends_on = None


def upgrade():
    """Fix ProductSKU id column to properly handle autoincrement"""

    connection = op.get_bind()

    # Check if product_sku table exists
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if 'product_sku' not in tables:
        print("   ⚠️  product_sku table doesn't exist, skipping")
        return

    print("   Fixing ProductSKU id column autoincrement...")

    try:
        # For SQLite, we need to recreate the table to fix autoincrement
        # First, create a temporary table with correct structure
        connection.execute(text("""
            CREATE TABLE product_sku_temp (
                id SERIAL PRIMARY KEY,
                inventory_item_id INTEGER,
                product_id INTEGER,
                variant_id INTEGER,
                size_label VARCHAR(32),
                sku_code VARCHAR(64),
                sku_name VARCHAR(128),
                unit VARCHAR(32),
                low_stock_threshold FLOAT,
                fifo_id VARCHAR(64),
                batch_id INTEGER,
                container_id INTEGER,
                retail_price FLOAT,
                wholesale_price FLOAT,
                profit_margin_target FLOAT,
                category VARCHAR(64),
                subcategory VARCHAR(64),
                tags TEXT,
                description TEXT,
                is_active BOOLEAN,
                is_product_active BOOLEAN,
                is_discontinued BOOLEAN,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                created_by INTEGER,
                supplier_name VARCHAR(128),
                supplier_sku VARCHAR(64),
                supplier_cost FLOAT,
                weight FLOAT,
                weight_unit VARCHAR(16),
                dimensions VARCHAR(64),
                barcode VARCHAR(64),
                upc VARCHAR(64),
                quality_status VARCHAR(32),
                compliance_status VARCHAR(32),
                quality_checked_by INTEGER,
                quality_checked_at TIMESTAMP,
                location_id INTEGER,
                location_name VARCHAR(128),
                temperature_at_time FLOAT,
                shopify_product_id VARCHAR(64),
                shopify_variant_id VARCHAR(64),
                etsy_listing_id VARCHAR(64),
                amazon_asin VARCHAR(64),
                marketplace_sync_status VARCHAR(32),
                marketplace_last_sync TIMESTAMP,
                expiration_date TIMESTAMP,
                is_perishable BOOLEAN,
                shelf_life_days INTEGER,
                organization_id INTEGER
            )
        """))

        # Copy data from old table to new table (excluding id to let autoincrement work)
        connection.execute(text("""
            INSERT INTO product_sku_temp (
                inventory_item_id, product_id, variant_id, size_label, sku_code, sku_name,
                unit, low_stock_threshold, fifo_id, batch_id, container_id,
                retail_price, wholesale_price, profit_margin_target, category, subcategory,
                tags, description, is_active, is_product_active, is_discontinued,
                created_at, updated_at, created_by, supplier_name, supplier_sku, supplier_cost,
                weight, weight_unit, dimensions, barcode, upc, quality_status, compliance_status,
                quality_checked_by, quality_checked_at, location_id, location_name,
                temperature_at_time, shopify_product_id, shopify_variant_id, etsy_listing_id,
                amazon_asin, marketplace_sync_status, marketplace_last_sync, expiration_date,
                is_perishable, shelf_life_days, organization_id
            )
            SELECT 
                inventory_item_id, product_id, variant_id, size_label, sku_code, sku_name,
                unit, low_stock_threshold, fifo_id, batch_id, container_id,
                retail_price, wholesale_price, profit_margin_target, category, subcategory,
                tags, description, is_active, is_product_active, is_discontinued,
                created_at, updated_at, created_by, supplier_name, supplier_sku, supplier_cost,
                weight, weight_unit, dimensions, barcode, upc, quality_status, compliance_status,
                quality_checked_by, quality_checked_at, location_id, location_name,
                temperature_at_time, shopify_product_id, shopify_variant_id, etsy_listing_id,
                amazon_asin, marketplace_sync_status, marketplace_last_sync, expiration_date,
                is_perishable, shelf_life_days, organization_id
            FROM product_sku
        """))

        # Drop old table and rename new one
        connection.execute(text("DROP TABLE product_sku"))
        connection.execute(text("ALTER TABLE product_sku_temp RENAME TO product_sku"))

        print("   ✅ Successfully fixed ProductSKU id column autoincrement")

    except Exception as e:
        print(f"   ⚠️  Error fixing ProductSKU id column: {e}")
        # Try to clean up if something went wrong
        try:
            connection.execute(text("DROP TABLE IF EXISTS product_sku_temp"))
        except:
            pass
        raise


def downgrade():
    """Revert ProductSKU id column changes"""
    # This downgrade recreates the table with the original problematic structure
    # In practice, this would be dangerous to run
    print("   ⚠️  Downgrade not implemented - would recreate problematic autoincrement")
    pass
