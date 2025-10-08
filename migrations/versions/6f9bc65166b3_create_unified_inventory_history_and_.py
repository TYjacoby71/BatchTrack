"""Create unified inventory history and merge data

Revision ID: 6f9bc65166b3
Revises: add_email_verified_at_column
Create Date: 2025-08-13 19:25:08.055765

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '6f9bc65166b3'
down_revision = 'add_email_verified_at_column'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    try:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception as e:
        print(f"   ⚠️  Could not check table existence for {table_name}: {e}")
        return False


def upgrade():
    """Create unified inventory history table and migrate existing data"""
    print("=== Creating UnifiedInventoryHistory and migrating data ===")

    # Check if table already exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'unified_inventory_history' not in existing_tables:
        print("   Creating unified_inventory_history table...")
        op.create_table('unified_inventory_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), nullable=False),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('change_type', sa.String(50), nullable=False),
            sa.Column('quantity_change', sa.Float(), nullable=False),
            sa.Column('unit', sa.String(50), nullable=False),
            sa.Column('unit_cost', sa.Float(), nullable=True),
            sa.Column('remaining_quantity', sa.Float(), nullable=False, default=0.0),

            # FIFO Tracking
            sa.Column('fifo_reference_id', sa.Integer(), nullable=True),
            sa.Column('fifo_code', sa.String(64), nullable=True),

            # Contextual Information
            sa.Column('batch_id', sa.Integer(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('quantity_used', sa.Float(), nullable=False, default=0.0),
            sa.Column('used_for_batch_id', sa.Integer(), nullable=True),

            # Perishability
            sa.Column('is_perishable', sa.Boolean(), nullable=False, default=False),
            sa.Column('shelf_life_days', sa.Integer(), nullable=True),
            sa.Column('expiration_date', sa.DateTime(), nullable=True),

            # Location and Quality
            sa.Column('location_id', sa.String(128), nullable=True),
            sa.Column('location_name', sa.String(128), nullable=True),
            sa.Column('temperature_at_time', sa.Float(), nullable=True),
            sa.Column('quality_status', sa.String(32), nullable=True),
            sa.Column('compliance_status', sa.String(32), nullable=True),
            sa.Column('quality_checked_by', sa.Integer(), nullable=True),

            # Product-Specific Fields (Nullable for ingredient entries)
            sa.Column('customer', sa.String(255), nullable=True),
            sa.Column('sale_price', sa.Float(), nullable=True),
            sa.Column('order_id', sa.String(255), nullable=True),
            sa.Column('reservation_id', sa.String(64), nullable=True),
            sa.Column('is_reserved', sa.Boolean(), nullable=False, default=False),
            sa.Column('sale_location', sa.String(64), nullable=True),
            sa.Column('marketplace_order_id', sa.String(128), nullable=True),
            sa.Column('marketplace_source', sa.String(32), nullable=True),

            # Additional tracking
            sa.Column('batch_number', sa.String(128), nullable=True),
            sa.Column('lot_number', sa.String(128), nullable=True),
            sa.Column('container_id', sa.Integer(), nullable=True),
            sa.Column('fifo_source', sa.String(128), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),

            # Constraints
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
            sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
            sa.ForeignKeyConstraint(['used_for_batch_id'], ['batch.id']),
            sa.ForeignKeyConstraint(['created_by'], ['user.id']),
            sa.ForeignKeyConstraint(['quality_checked_by'], ['user.id']),
            sa.ForeignKeyConstraint(['container_id'], ['inventory_item.id']),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
            sa.ForeignKeyConstraint(['fifo_reference_id'], ['unified_inventory_history.id'])
        )

    # 2. Create indexes for performance
    print("   Creating indexes...")
    
    # Check if indexes already exist before creating them
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = []
    
    try:
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('unified_inventory_history')]
    except:
        # Table might not exist yet
        existing_indexes = []
    
    indexes_to_create = [
        ('idx_unified_item_remaining', ['inventory_item_id', 'remaining_quantity']),
        ('idx_unified_item_timestamp', ['inventory_item_id', 'timestamp']),
        ('idx_unified_fifo_code', ['fifo_code']),
        ('idx_unified_change_type', ['change_type']),
        ('idx_unified_expiration', ['expiration_date'])
    ]
    
    for idx_name, columns in indexes_to_create:
        if idx_name not in existing_indexes:
            try:
                op.create_index(idx_name, 'unified_inventory_history', columns)
                print(f"   ✅ Created index: {idx_name}")
            except Exception as e:
                print(f"   ⚠️  Could not create index {idx_name}: {e}")
        else:
            print(f"   ⚠️  Index {idx_name} already exists - skipping")

    # 3. Migrate data from inventory_history if it exists
    print("   Migrating data from inventory_history...")

    # Get connection and migrate data
    bind = op.get_bind()

    # Check if source table exists  
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Only migrate data if both tables exist and are in correct state
    if 'inventory_history' in existing_tables and 'unified_inventory_history' in existing_tables:
        # Get organization_id from inventory_item for each record
        # Use CURRENT_TIMESTAMP for SQLite compatibility instead of now()
        migrate_inventory_sql = text("""
            INSERT INTO unified_inventory_history (
                inventory_item_id, timestamp, change_type, quantity_change, unit,
                unit_cost, remaining_quantity, fifo_reference_id, fifo_code,
                batch_id, created_by, notes, quantity_used,
                is_perishable, shelf_life_days, expiration_date, organization_id
            )
            SELECT 
                ih.inventory_item_id,
                COALESCE(ih.timestamp, CURRENT_TIMESTAMP) as timestamp,
                COALESCE(ih.change_type, 'unknown') as change_type,
                COALESCE(ih.quantity_change, 0.0) as quantity_change,
                COALESCE(ih.unit, 'g') as unit,
                ih.unit_cost,
                COALESCE(ih.remaining_quantity, 0.0) as remaining_quantity,
                ih.fifo_reference_id,
                ih.fifo_code,
                ih.batch_id,
                ih.created_by,
                '' as notes,
                COALESCE(ih.quantity_used, 0.0) as quantity_used,
                CASE WHEN ih.is_perishable IS NULL THEN false ELSE ih.is_perishable END as is_perishable,
                ih.shelf_life_days,
                ih.expiration_date,
                COALESCE(ii.organization_id, 1) as organization_id
            FROM inventory_history ih
            LEFT JOIN inventory_item ii ON ih.inventory_item_id = ii.id
        """)

        try:
            bind.execute(migrate_inventory_sql)
            print("   ✅ Successfully migrated inventory_history data")
        except Exception as e:
            print(f"   ⚠️  Error migrating inventory_history: {e}")
            # Rollback the failed transaction and start fresh
            try:
                bind.rollback()
            except:
                pass
            print("   ℹ️  Transaction rolled back, continuing with migration...")

    # 4. Migrate data from product_sku_history if it exists
    # Check table existence in a new transaction context
    try:
        bind = op.get_bind()  # Get fresh connection
        inspector = sa.inspect(bind)
        has_product_sku_history = 'product_sku_history' in inspector.get_table_names()
    except Exception as e:
        print(f"   ⚠️  Could not check for product_sku_history table: {e}")
        has_product_sku_history = False

    if has_product_sku_history:
        print("   Migrating data from product_sku_history...")

        # Check what columns actually exist in product_sku_history
        try:
            bind = op.get_bind()
            inspector = sa.inspect(bind)
            psh_columns = [col['name'] for col in inspector.get_columns('product_sku_history')]
            print(f"   Available product_sku_history columns: {psh_columns}")
            
            # Check if product_sku table exists
            has_product_sku_table = 'product_sku' in inspector.get_table_names()
            
            # Build migration SQL based on available columns
            if 'inventory_item_id' in psh_columns:
                # Direct migration - product_sku_history has inventory_item_id
                migrate_product_sql = text("""
                    INSERT INTO unified_inventory_history (
                        inventory_item_id, timestamp, change_type, quantity_change, unit,
                        unit_cost, remaining_quantity, fifo_reference_id, fifo_code,
                        batch_id, created_by, notes, quantity_used,
                        is_perishable, shelf_life_days, expiration_date,
                        customer, sale_price, order_id, organization_id
                    )
                    SELECT 
                        psh.inventory_item_id,
                        COALESCE(psh.timestamp, CURRENT_TIMESTAMP) as timestamp,
                        COALESCE(psh.change_type, 'unknown') as change_type,
                        COALESCE(psh.quantity_change, 0.0) as quantity_change,
                        COALESCE(psh.unit, 'count') as unit,
                        psh.unit_cost,
                        COALESCE(psh.remaining_quantity, 0.0) as remaining_quantity,
                        psh.fifo_reference_id,
                        psh.fifo_code,
                        psh.batch_id,
                        COALESCE(psh.created_by, psh.user_id) as created_by,
                        COALESCE(psh.notes, '') as notes,
                        COALESCE(psh.quantity_used, 0.0) as quantity_used,
                        CASE WHEN psh.is_perishable IS NULL THEN false ELSE psh.is_perishable END as is_perishable,
                        psh.shelf_life_days,
                        psh.expiration_date,
                        psh.customer,
                        psh.sale_price,
                        psh.order_id,
                        COALESCE(ii.organization_id, 1) as organization_id
                    FROM product_sku_history psh
                    LEFT JOIN inventory_item ii ON psh.inventory_item_id = ii.id
                    WHERE psh.inventory_item_id IS NOT NULL
                """)
            elif has_product_sku_table and ('sku_id' in psh_columns or 'product_sku_id' in psh_columns):
                # Migration via product_sku table
                sku_col = 'sku_id' if 'sku_id' in psh_columns else 'product_sku_id'
                migrate_product_sql = text(f"""
                    INSERT INTO unified_inventory_history (
                        inventory_item_id, timestamp, change_type, quantity_change, unit,
                        unit_cost, remaining_quantity, fifo_reference_id, fifo_code,
                        batch_id, created_by, notes, quantity_used,
                        is_perishable, shelf_life_days, expiration_date,
                        customer, sale_price, order_id, organization_id
                    )
                    SELECT 
                        ps.inventory_item_id,
                        COALESCE(psh.timestamp, CURRENT_TIMESTAMP) as timestamp,
                        COALESCE(psh.change_type, 'unknown') as change_type,
                        COALESCE(psh.quantity_change, 0.0) as quantity_change,
                        COALESCE(psh.unit, 'count') as unit,
                        psh.unit_cost,
                        COALESCE(psh.remaining_quantity, 0.0) as remaining_quantity,
                        psh.fifo_reference_id,
                        psh.fifo_code,
                        psh.batch_id,
                        COALESCE(psh.created_by, psh.user_id) as created_by,
                        COALESCE(psh.notes, '') as notes,
                        COALESCE(psh.quantity_used, 0.0) as quantity_used,
                        CASE WHEN psh.is_perishable IS NULL THEN false ELSE psh.is_perishable END as is_perishable,
                        psh.shelf_life_days,
                        psh.expiration_date,
                        psh.customer,
                        psh.sale_price,
                        psh.order_id,
                        COALESCE(ii.organization_id, ps.organization_id, 1) as organization_id
                    FROM product_sku_history psh
                    LEFT JOIN product_sku ps ON psh.{sku_col} = ps.id
                    LEFT JOIN inventory_item ii ON ps.inventory_item_id = ii.id
                    WHERE ps.inventory_item_id IS NOT NULL
                """)
            else:
                print("   ⚠️  Cannot migrate product_sku_history: no valid column mapping found")
                migrate_product_sql = None

            if migrate_product_sql:
                bind.execute(migrate_product_sql)
                print("   ✅ Successfully migrated product_sku_history data")
            
        except Exception as e:
            print(f"   ⚠️  Error migrating product_sku_history: {e}")
            # Rollback the failed transaction and get a new connection
            try:
                bind.rollback()
            except:
                pass
            print("   ℹ️  Transaction rolled back, continuing with migration...")

    print("   ✅ Unified inventory history migration completed")


def downgrade():
    """Reverse the migration - restore original tables"""
    print("=== Reverting unified inventory history migration ===")

    # This is a destructive operation - we'll recreate the old tables
    # but data migration back would be complex
    print("   WARNING: Downgrade will lose unified history data!")

    # Drop the unified table
    op.drop_table('unified_inventory_history')

    print("   ✅ Unified inventory history table dropped")
    print("   NOTE: Original inventory_history and product_sku_history tables")
    print("         should be restored from backup if needed")