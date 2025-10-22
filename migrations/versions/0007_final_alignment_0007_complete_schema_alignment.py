"""0007 complete schema alignment

Revision ID: 0007_final_alignment
Revises: 0006_schema_alignment
Create Date: 2025-01-22 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_final_alignment'
down_revision = '0006_schema_alignment'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. Handle nullable constraints that were detected
    if dialect == 'sqlite':
        with op.batch_alter_table('inventory_item', schema=None) as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), nullable=True)
            batch_op.alter_column('is_archived', existing_type=sa.Boolean(), nullable=True)
        with op.batch_alter_table('role', schema=None) as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), nullable=True)
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), nullable=True)
    else:
        op.alter_column('inventory_item', 'is_active', existing_type=sa.Boolean(), nullable=True)
        op.alter_column('inventory_item', 'is_archived', existing_type=sa.Boolean(), nullable=True)
        op.alter_column('role', 'is_active', existing_type=sa.Boolean(), nullable=True)
        op.alter_column('user', 'is_active', existing_type=sa.Boolean(), nullable=True)

    # 2. Add missing indexes that were detected

    # PostgreSQL-specific indexes
    if dialect == 'postgresql':
        # GIN indexes for JSON columns
        try:
            op.execute('CREATE INDEX IF NOT EXISTS ix_global_item_aka_gin ON global_item USING gin ((aka_names::jsonb));')
        except:
            pass  # Index may already exist

        try:
            op.execute('CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING gin ((category_data::jsonb));')
        except:
            pass  # Index may already exist

        # Text search index for global_item_alias using 'simple' config
        try:
            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv 
                ON global_item_alias USING gin(to_tsvector('simple', alias));
            """)
        except:
            pass  # Index may already exist

        # Case-insensitive unique index for product_category names
        try:
            op.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name));')
        except:
            pass  # Index may already exist

    # 3. Handle index changes

    # Remove old inventory_item name_org index (was created in 0002)
    try:
        op.drop_index('ix_inventory_item_name_org', table_name='inventory_item')
    except:
        pass  # May not exist

    # Remove old product_sku sku index and add unique constraint
    try:
        op.drop_index('ix_product_sku_sku', table_name='product_sku')
    except:
        pass  # May not exist

    # Add unique constraint on product_sku.sku
    try:
        op.create_unique_constraint(None, 'product_sku', ['sku'])
    except:
        pass  # May already exist

    # Add missing foreign key to product_sku (quality_checked_by)
    try:
        op.create_foreign_key(None, 'product_sku', 'user', ['quality_checked_by'], ['id'])
    except:
        pass  # May already exist

    # Remove stripe_event event_type index (created in 0002)
    try:
        op.drop_index('ix_stripe_event_event_type', table_name='stripe_event')
    except:
        pass  # May not exist


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Restore stripe_event index
    try:
        op.create_index('ix_stripe_event_event_type', 'stripe_event', ['event_type'], unique=False)
    except:
        pass

    # Remove product_sku foreign key and unique constraint
    try:
        op.drop_constraint(None, 'product_sku', type_='foreignkey')  # quality_checked_by FK
    except:
        pass
    try:
        op.drop_constraint(None, 'product_sku', type_='unique')  # sku unique constraint
    except:
        pass

    # Restore product_sku sku index
    try:
        op.create_index('ix_product_sku_sku', 'product_sku', ['sku'], unique=True)
    except:
        pass

    # Restore inventory_item name_org index  
    try:
        op.create_index('ix_inventory_item_name_org', 'inventory_item', ['organization_id', 'name'], unique=True)
    except:
        pass

    # Drop PostgreSQL-specific indexes
    if dialect == 'postgresql':
        indexes_to_drop = [
            'ix_product_category_lower_name',
            'ix_global_item_alias_tsv', 
            'ix_recipe_category_data_gin',
            'ix_global_item_aka_gin'
        ]

        for idx_name in indexes_to_drop:
            try:
                op.drop_index(idx_name)
            except:
                pass

    # Restore nullable constraints to non-nullable with defaults
    if dialect == 'sqlite':
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
        with op.batch_alter_table('role', schema=None) as batch_op:
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
        with op.batch_alter_table('inventory_item', schema=None) as batch_op:
            batch_op.alter_column('is_archived', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
            batch_op.alter_column('is_active', existing_type=sa.Boolean(), nullable=False, server_default=sa.true())
    else:
        op.alter_column('user', 'is_active', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
        op.alter_column('role', 'is_active', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
        op.alter_column('inventory_item', 'is_archived', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
        op.alter_column('inventory_item', 'is_active', existing_type=sa.Boolean(), nullable=False, server_default=sa.true())