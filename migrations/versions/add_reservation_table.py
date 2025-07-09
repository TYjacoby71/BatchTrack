
"""Add reservation table for new reservation system

Revision ID: add_reservation_table
Revises: aa271449bf33
Create Date: 2025-07-09 19:35:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'add_reservation_table'
down_revision = 'aa271449bf33'
branch_labels = None
depends_on = None

def upgrade():
    # Create reservation table
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
    
    # Create indexes
    op.create_index('idx_order_status', 'reservation', ['order_id', 'status'], unique=False)
    op.create_index('idx_reserved_item_status', 'reservation', ['reserved_item_id', 'status'], unique=False)
    op.create_index('idx_expires_at', 'reservation', ['expires_at'], unique=False)
    op.create_index(op.f('ix_reservation_order_id'), 'reservation', ['order_id'], unique=False)

def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_reservation_order_id'), table_name='reservation')
    op.drop_index('idx_expires_at', table_name='reservation')
    op.drop_index('idx_reserved_item_status', table_name='reservation')
    op.drop_index('idx_order_status', table_name='reservation')
    
    # Drop table
    op.drop_table('reservation')
