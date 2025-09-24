"""Production bootstrap 0004 - lots, unified history, events, freshness, stats

Revision ID: prod_0004_lots_history
Revises: prod_0003_recipe_batch
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'prod_0004_lots_history'
down_revision = 'prod_0003_recipe_batch'
branch_labels = ('production_bootstrap',)
depends_on = None


def upgrade():
    # Inventory lot
    op.create_table(
        'inventory_lot',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('remaining_quantity', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('original_quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('received_date', sa.DateTime(), nullable=False),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('fifo_code', sa.String(length=32), nullable=True, unique=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.CheckConstraint('remaining_quantity >= 0', name='check_remaining_quantity_non_negative'),
        sa.CheckConstraint('original_quantity > 0', name='check_original_quantity_positive'),
        sa.CheckConstraint('remaining_quantity <= original_quantity', name='check_remaining_not_exceeds_original'),
    )
    op.create_index('idx_inventory_lot_received_date', 'inventory_lot', ['received_date'])
    op.create_index('idx_inventory_lot_organization', 'inventory_lot', ['organization_id'])
    op.create_index('idx_inventory_lot_item_remaining', 'inventory_lot', ['inventory_item_id', 'remaining_quantity'])
    op.create_index('idx_inventory_lot_expiration', 'inventory_lot', ['expiration_date'])
    op.create_index('idx_inventory_lot_batch', 'inventory_lot', ['batch_id'])

    # Unified inventory history (references lot and others)
    op.create_table(
        'unified_inventory_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('change_type', sa.String(length=50), nullable=False),
        sa.Column('quantity_change', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('affected_lot_id', sa.Integer(), nullable=True),
        sa.Column('remaining_quantity', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('unit_cost', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('valuation_method', sa.String(length=16), nullable=True),
        sa.Column('fifo_reference_id', sa.Integer(), nullable=True),
        sa.Column('fifo_code', sa.String(length=32), nullable=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('quantity_used', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('used_for_batch_id', sa.Integer(), nullable=True),
        sa.Column('is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('location_id', sa.String(length=128), nullable=True),
        sa.Column('location_name', sa.String(length=128), nullable=True),
        sa.Column('temperature_at_time', sa.Float(), nullable=True),
        sa.Column('quality_status', sa.String(length=32), nullable=True),
        sa.Column('compliance_status', sa.String(length=32), nullable=True),
        sa.Column('quality_checked_by', sa.Integer(), nullable=True),
        sa.Column('customer', sa.String(length=255), nullable=True),
        sa.Column('sale_price', sa.Float(), nullable=True),
        sa.Column('order_id', sa.String(length=255), nullable=True),
        sa.Column('reservation_id', sa.String(length=64), nullable=True),
        sa.Column('is_reserved', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('sale_location', sa.String(length=64), nullable=True),
        sa.Column('marketplace_order_id', sa.String(length=128), nullable=True),
        sa.Column('marketplace_source', sa.String(length=32), nullable=True),
        sa.Column('batch_number', sa.String(length=128), nullable=True),
        sa.Column('lot_number', sa.String(length=128), nullable=True),
        sa.Column('container_id', sa.Integer(), nullable=True),
        sa.Column('fifo_source', sa.String(length=128), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['affected_lot_id'], ['inventory_lot.id']),
        sa.ForeignKeyConstraint(['fifo_reference_id'], ['unified_inventory_history.id']),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['used_for_batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['quality_checked_by'], ['user.id']),
        sa.ForeignKeyConstraint(['container_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )
    op.create_index('idx_unified_item_remaining', 'unified_inventory_history', ['inventory_item_id', 'remaining_quantity'])
    op.create_index('idx_unified_item_timestamp', 'unified_inventory_history', ['inventory_item_id', 'timestamp'])
    op.create_index('idx_unified_fifo_code', 'unified_inventory_history', ['fifo_code'])
    op.create_index('idx_unified_change_type', 'unified_inventory_history', ['change_type'])
    op.create_index('idx_unified_expiration', 'unified_inventory_history', ['expiration_date'])

    # Classic inventory history (still referenced by some analytics code)
    op.create_table(
        'inventory_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('change_type', sa.String(length=50), nullable=True),
        sa.Column('quantity_change', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('remaining_quantity', sa.Float(), nullable=True),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('fifo_reference_id', sa.Integer(), nullable=True),
        sa.Column('fifo_code', sa.String(length=32), nullable=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('quantity_used', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('used_for_batch_id', sa.Integer(), nullable=True),
        sa.Column('is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['fifo_reference_id'], ['inventory_history.id']),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['used_for_batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    # Domain events and freshness snapshot
    op.create_table(
        'domain_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_name', sa.String(length=128), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(length=64), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('correlation_id', sa.String(length=128), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True, server_default=sa.text("'app'")),
        sa.Column('schema_version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('delivery_attempts', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index('ix_domain_event_event_name', 'domain_event', ['event_name'])
    op.create_index('ix_domain_event_occurred_at', 'domain_event', ['occurred_at'])
    op.create_index('ix_domain_event_org', 'domain_event', ['organization_id'])
    op.create_index('ix_domain_event_user', 'domain_event', ['user_id'])
    op.create_index('ix_domain_event_entity', 'domain_event', ['entity_type', 'entity_id'])
    op.create_index('ix_domain_event_is_processed', 'domain_event', ['is_processed'])
    op.create_index('ix_domain_event_correlation_id', 'domain_event', ['correlation_id'])

    op.create_table(
        'freshness_snapshot',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('avg_days_to_usage', sa.Float(), nullable=True),
        sa.Column('avg_days_to_spoilage', sa.Float(), nullable=True),
        sa.Column('freshness_efficiency_score', sa.Float(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.UniqueConstraint('snapshot_date', 'organization_id', 'inventory_item_id', name='uq_freshness_snapshot_unique'),
    )
    op.create_index('ix_freshness_snapshot_date', 'freshness_snapshot', ['snapshot_date'])
    op.create_index('ix_freshness_snapshot_org', 'freshness_snapshot', ['organization_id'])
    op.create_index('ix_freshness_snapshot_item', 'freshness_snapshot', ['inventory_item_id'])

    # Statistics tables
    op.create_table(
        'user_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('total_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('completed_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('failed_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cancelled_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_recipes', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('recipes_created', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('inventory_adjustments', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('inventory_items_created', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('products_created', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_products_made', sa.Float(), nullable=True, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'organization_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('total_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('completed_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('failed_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cancelled_batches', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_users', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('active_users', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_recipes', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_inventory_items', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_inventory_value', sa.Float(), nullable=True, server_default='0'),
        sa.Column('total_products', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_products_made', sa.Float(), nullable=True, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'batch_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('planned_fill_efficiency', sa.Float(), nullable=True, server_default='0'),
        sa.Column('actual_fill_efficiency', sa.Float(), nullable=True, server_default='0'),
        sa.Column('efficiency_variance', sa.Float(), nullable=True, server_default='0'),
        sa.Column('planned_yield_amount', sa.Float(), nullable=True, server_default='0'),
        sa.Column('planned_yield_unit', sa.String(length=50), nullable=True),
        sa.Column('actual_yield_amount', sa.Float(), nullable=True, server_default='0'),
        sa.Column('actual_yield_unit', sa.String(length=50), nullable=True),
        sa.Column('yield_variance_percentage', sa.Float(), nullable=True, server_default='0'),
        sa.Column('planned_ingredient_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('actual_ingredient_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('planned_container_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('actual_container_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('total_planned_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('total_actual_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('ingredient_spoilage_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('product_spoilage_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('waste_percentage', sa.Float(), nullable=True, server_default='0'),
        sa.Column('planned_duration_minutes', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('actual_duration_minutes', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('duration_variance_percentage', sa.Float(), nullable=True, server_default='0'),
        sa.Column('batch_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
    )

    op.create_table(
        'recipe_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipe_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('total_batches_planned', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_batches_completed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_batches_failed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('success_rate_percentage', sa.Float(), nullable=True, server_default='0'),
        sa.Column('avg_fill_efficiency', sa.Float(), nullable=True, server_default='0'),
        sa.Column('avg_yield_variance', sa.Float(), nullable=True, server_default='0'),
        sa.Column('avg_cost_variance', sa.Float(), nullable=True, server_default='0'),
        sa.Column('avg_cost_per_batch', sa.Float(), nullable=True, server_default='0'),
        sa.Column('avg_cost_per_unit', sa.Float(), nullable=True, server_default='0'),
        sa.Column('total_spoilage_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('most_used_container_id', sa.Integer(), nullable=True),
        sa.Column('avg_containers_needed', sa.Float(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_batch_date', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['most_used_container_id'], ['inventory_item.id']),
    )

    op.create_table(
        'inventory_change_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('change_type', sa.String(length=50), nullable=False),
        sa.Column('change_category', sa.String(length=50), nullable=False),
        sa.Column('quantity_change', sa.Float(), nullable=False),
        sa.Column('cost_impact', sa.Float(), nullable=True, server_default='0'),
        sa.Column('related_batch_id', sa.Integer(), nullable=True),
        sa.Column('related_lot_id', sa.Integer(), nullable=True),
        sa.Column('reason_code', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('item_age_days', sa.Integer(), nullable=True),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('freshness_score', sa.Float(), nullable=True),
        sa.Column('change_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['related_batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['related_lot_id'], ['inventory_lot.id']),
    )


def downgrade():
    op.drop_table('inventory_change_log')
    op.drop_table('recipe_stats')
    op.drop_table('batch_stats')
    op.drop_table('organization_stats')
    op.drop_index('ix_freshness_snapshot_item', table_name='freshness_snapshot')
    op.drop_index('ix_freshness_snapshot_org', table_name='freshness_snapshot')
    op.drop_index('ix_freshness_snapshot_date', table_name='freshness_snapshot')
    op.drop_table('freshness_snapshot')
    op.drop_index('ix_domain_event_correlation_id', table_name='domain_event')
    op.drop_index('ix_domain_event_is_processed', table_name='domain_event')
    op.drop_index('ix_domain_event_entity', table_name='domain_event')
    op.drop_index('ix_domain_event_user', table_name='domain_event')
    op.drop_index('ix_domain_event_org', table_name='domain_event')
    op.drop_index('ix_domain_event_occurred_at', table_name='domain_event')
    op.drop_index('ix_domain_event_event_name', table_name='domain_event')
    op.drop_table('domain_event')
    op.drop_table('inventory_history')
    op.drop_index('idx_unified_expiration', table_name='unified_inventory_history')
    op.drop_index('idx_unified_change_type', table_name='unified_inventory_history')
    op.drop_index('idx_unified_fifo_code', table_name='unified_inventory_history')
    op.drop_index('idx_unified_item_timestamp', table_name='unified_inventory_history')
    op.drop_index('idx_unified_item_remaining', table_name='unified_inventory_history')
    op.drop_table('unified_inventory_history')
    op.drop_index('idx_inventory_lot_batch', table_name='inventory_lot')
    op.drop_index('idx_inventory_lot_expiration', table_name='inventory_lot')
    op.drop_index('idx_inventory_lot_item_remaining', table_name='inventory_lot')
    op.drop_index('idx_inventory_lot_organization', table_name='inventory_lot')
    op.drop_index('idx_inventory_lot_received_date', table_name='inventory_lot')
    op.drop_table('inventory_lot')

