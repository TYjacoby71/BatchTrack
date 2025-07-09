"""Consolidate reservation system and role/permission changes

Revision ID: 9bc15ea2061a
Revises: aa271449bf33
Create Date: 2025-01-09 19:55:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '6e0c5e2e1c48'
down_revision = 'aa271449bf33'
branch_labels = None
depends_on = None

def upgrade():
    # Create reservation table if it doesn't exist
    try:
        op.create_table('reservation',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.String(length=128), nullable=False),
            sa.Column('reservation_id', sa.String(length=128), nullable=True),
            sa.Column('product_item_id', sa.Integer(), nullable=False),
            sa.Column('reserved_item_id', sa.Integer(), nullable=False),
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('unit', sa.String(length=32), nullable=False),
            sa.Column('unit_cost', sa.Float(), nullable=True),
            sa.Column('sale_price', sa.Float(), nullable=True),
            sa.Column('source_fifo_id', sa.Integer(), nullable=True),
            sa.Column('source_batch_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=True),
            sa.Column('source', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('released_at', sa.DateTime(), nullable=True),
            sa.Column('converted_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
            sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
            sa.ForeignKeyConstraint(['product_item_id'], ['inventory_item.id'], ),
            sa.ForeignKeyConstraint(['reserved_item_id'], ['inventory_item.id'], ),
            sa.ForeignKeyConstraint(['source_batch_id'], ['batch.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

        # Create indexes for reservation table
        op.create_index('idx_order_status', 'reservation', ['order_id', 'status'], unique=False)
        op.create_index('idx_reserved_item_status', 'reservation', ['reserved_item_id', 'status'], unique=False)
        op.create_index('idx_expires_at', 'reservation', ['expires_at'], unique=False)
        op.create_index(op.f('ix_reservation_order_id'), 'reservation', ['order_id'], unique=False)
    except Exception as e:
        print(f"Reservation table might already exist: {e}")
        pass

    # Remove original_quantity column from product_sku_history if it exists
    try:
        with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
            batch_op.drop_column('original_quantity')
    except Exception as e:
        print(f"original_quantity column might not exist: {e}")
        pass

def downgrade():
    # Drop reservation table and indexes
    try:
        op.drop_index(op.f('ix_reservation_order_id'), table_name='reservation')
        op.drop_index('idx_expires_at', table_name='reservation')
        op.drop_index('idx_reserved_item_status', table_name='reservation')
        op.drop_index('idx_order_status', table_name='reservation')
        op.drop_table('reservation')
    except:
        pass

    # Add back original_quantity column to product_sku_history
    try:
        with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
            batch_op.add_column(sa.Column('original_quantity', sa.Float(), nullable=True))
    except:
        pass