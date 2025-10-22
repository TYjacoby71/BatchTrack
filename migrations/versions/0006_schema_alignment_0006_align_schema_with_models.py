
"""0006 align schema with models

Revision ID: 0006_schema_alignment
Revises: 0005_cleanup_guardrails
Create Date: 2025-01-22 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_schema_alignment'
down_revision = '0005_cleanup_guardrails'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. Create reservation table matching current models
    op.create_table('reservation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.String(length=128), nullable=False),
        sa.Column('reserved_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('reservation_id', sa.String(length=128), nullable=True),
        sa.Column('product_item_id', sa.Integer(), nullable=True),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('sale_price', sa.Float(), nullable=True),
        sa.Column('customer', sa.String(length=255), nullable=True),
        sa.Column('source_fifo_id', sa.String(length=128), nullable=True),
        sa.Column('source_batch_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('converted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['reserved_item_id'], ['inventory_item.id'], ),
        sa.ForeignKeyConstraint(['product_item_id'], ['inventory_item.id'], ),
        sa.ForeignKeyConstraint(['source_batch_id'], ['batch.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add reservation indexes
    op.create_index('idx_expires_at', 'reservation', ['expires_at'], unique=False)
    op.create_index('idx_order_status', 'reservation', ['order_id', 'status'], unique=False)
    op.create_index('idx_reserved_item_status', 'reservation', ['reserved_item_id', 'status'], unique=False)
    op.create_index(op.f('ix_reservation_order_id'), 'reservation', ['order_id'], unique=False)

    # 2. Fix nullable constraints (reverse what 0005 did for columns that should be nullable)
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
    op.create_unique_constraint(None, 'product_sku', ['sku'])

    # Add missing foreign key to product_sku
    try:
        op.create_foreign_key(None, 'product_sku', 'user', ['quality_checked_by'], ['id'])
    except:
        pass  # May already exist

    # Remove stripe_event event_type index (created in 0002)
    try:
        op.drop_index('ix_stripe_event_event_type', table_name='stripe_event')
    except:
        pass  # May not exist

    # 4. Add PostgreSQL-specific indexes and features
    if dialect == 'postgresql':
        # Add GIN indexes for JSON columns and text search
        # Note: Cannot use CONCURRENTLY within transaction, so using regular CREATE INDEX
        op.execute('CREATE INDEX ix_global_item_aka_gin ON global_item USING gin ((aka_names::jsonb));')
        op.execute('CREATE INDEX ix_recipe_category_data_gin ON recipe USING gin ((category_data::jsonb));')

        # Add text search index for global_item_alias using 'simple' config
        op.execute("""
            CREATE INDEX ix_global_item_alias_tsv ON global_item_alias 
            USING gin(to_tsvector('simple', alias));
        """)

        # Add UNIQUE case-insensitive index for product_category names
        op.execute('CREATE UNIQUE INDEX ix_product_category_lower_name ON product_category (lower(name));')


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop PostgreSQL-specific indexes
    if dialect == 'postgresql':
        try:
            op.drop_index('ix_product_category_lower_name', table_name='product_category')
        except:
            pass
        try:
            op.drop_index('ix_global_item_alias_tsv', table_name='global_item_alias')
        except:
            pass
        try:
            op.drop_index('ix_recipe_category_data_gin', table_name='recipe')
        except:
            pass
        try:
            op.drop_index('ix_global_item_aka_gin', table_name='global_item')
        except:
            pass

    # Restore stripe_event index
    op.create_index('ix_stripe_event_event_type', 'stripe_event', ['event_type'], unique=False)

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
    op.create_index('ix_product_sku_sku', 'product_sku', ['sku'], unique=True)

    # Restore inventory_item name_org index  
    op.create_index('ix_inventory_item_name_org', 'inventory_item', ['organization_id', 'name'], unique=True)

    # Restore nullable constraints
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

    # Drop reservation table and indexes
    op.drop_index(op.f('ix_reservation_order_id'), table_name='reservation')
    op.drop_index('idx_reserved_item_status', table_name='reservation')
    op.drop_index('idx_order_status', table_name='reservation')
    op.drop_index('idx_expires_at', table_name='reservation')
    op.drop_table('reservation')
