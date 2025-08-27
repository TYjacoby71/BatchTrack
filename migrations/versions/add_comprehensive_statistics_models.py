"""Add comprehensive statistics models

Revision ID: add_comprehensive_stats
Revises: latest
Create Date: 2025-08-27 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_comprehensive_stats'
down_revision = None  # Replace with actual latest revision
branch_labels = None
depends_on = None

def upgrade():
    """Create comprehensive statistics tables"""

    # BatchStats table
    op.create_table('batch_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('planned_fill_efficiency', sa.Float(), default=0.0),
        sa.Column('actual_fill_efficiency', sa.Float(), default=0.0),
        sa.Column('efficiency_variance', sa.Float(), default=0.0),
        sa.Column('planned_yield_amount', sa.Float(), default=0.0),
        sa.Column('planned_yield_unit', sa.String(50)),
        sa.Column('actual_yield_amount', sa.Float(), default=0.0),
        sa.Column('actual_yield_unit', sa.String(50)),
        sa.Column('yield_variance_percentage', sa.Float(), default=0.0),
        sa.Column('planned_ingredient_cost', sa.Float(), default=0.0),
        sa.Column('actual_ingredient_cost', sa.Float(), default=0.0),
        sa.Column('planned_container_cost', sa.Float(), default=0.0),
        sa.Column('actual_container_cost', sa.Float(), default=0.0),
        sa.Column('total_planned_cost', sa.Float(), default=0.0),
        sa.Column('total_actual_cost', sa.Float(), default=0.0),
        sa.Column('cost_variance_percentage', sa.Float(), default=0.0),
        sa.Column('ingredient_spoilage_cost', sa.Float(), default=0.0),
        sa.Column('product_spoilage_cost', sa.Float(), default=0.0),
        sa.Column('waste_percentage', sa.Float(), default=0.0),
        sa.Column('planned_duration_minutes', sa.Integer(), default=0),
        sa.Column('actual_duration_minutes', sa.Integer(), default=0),
        sa.Column('duration_variance_percentage', sa.Float(), default=0.0),
        sa.Column('batch_status', sa.String(50)),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('last_updated', sa.DateTime()),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_id')
    )

    # RecipeStats table
    op.create_table('recipe_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('total_batches_planned', sa.Integer(), default=0),
        sa.Column('total_batches_completed', sa.Integer(), default=0),
        sa.Column('total_batches_failed', sa.Integer(), default=0),
        sa.Column('success_rate_percentage', sa.Float(), default=0.0),
        sa.Column('avg_fill_efficiency', sa.Float(), default=0.0),
        sa.Column('avg_yield_variance', sa.Float(), default=0.0),
        sa.Column('avg_cost_variance', sa.Float(), default=0.0),
        sa.Column('avg_cost_per_batch', sa.Float(), default=0.0),
        sa.Column('avg_cost_per_unit', sa.Float(), default=0.0),
        sa.Column('total_spoilage_cost', sa.Float(), default=0.0),
        sa.Column('most_used_container_id', sa.Integer()),
        sa.Column('avg_containers_needed', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('last_batch_date', sa.DateTime()),
        sa.Column('last_updated', sa.DateTime()),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['most_used_container_id'], ['inventory_item.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id')
    )

    # InventoryEfficiencyStats table
    op.create_table('inventory_efficiency_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('total_purchased_quantity', sa.Float(), default=0.0),
        sa.Column('total_used_quantity', sa.Float(), default=0.0),
        sa.Column('total_spoiled_quantity', sa.Float(), default=0.0),
        sa.Column('total_wasted_quantity', sa.Float(), default=0.0),
        sa.Column('utilization_percentage', sa.Float(), default=0.0),
        sa.Column('spoilage_rate', sa.Float(), default=0.0),
        sa.Column('waste_rate', sa.Float(), default=0.0),
        sa.Column('total_purchase_cost', sa.Float(), default=0.0),
        sa.Column('total_spoilage_cost', sa.Float(), default=0.0),
        sa.Column('total_waste_cost', sa.Float(), default=0.0),
        sa.Column('effective_cost_per_unit', sa.Float(), default=0.0),
        sa.Column('avg_days_to_use', sa.Float(), default=0.0),
        sa.Column('avg_days_to_spoil', sa.Float(), default=0.0),
        sa.Column('freshness_score', sa.Float(), default=100.0),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('last_updated', sa.DateTime()),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inventory_item_id')
    )

    # OrganizationLeaderboardStats table  
    op.create_table('organization_leaderboard_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('total_recipes', sa.Integer(), default=0),
        sa.Column('active_recipes_count', sa.Integer(), default=0),
        sa.Column('most_popular_recipe_id', sa.Integer()),
        sa.Column('avg_recipe_success_rate', sa.Float(), default=0.0),
        sa.Column('total_batches_completed', sa.Integer(), default=0),
        sa.Column('avg_batch_completion_time', sa.Float(), default=0.0),
        sa.Column('avg_fill_efficiency', sa.Float(), default=0.0),
        sa.Column('highest_fill_efficiency', sa.Float(), default=0.0),
        sa.Column('active_users_count', sa.Integer(), default=0),
        sa.Column('most_productive_user_id', sa.Integer()),
        sa.Column('avg_batches_per_user', sa.Float(), default=0.0),
        sa.Column('most_used_container_size', sa.Float(), default=0.0),
        sa.Column('most_used_container_id', sa.Integer()),
        sa.Column('avg_cost_per_batch', sa.Float(), default=0.0),
        sa.Column('lowest_cost_per_unit', sa.Float(), default=0.0),
        sa.Column('highest_cost_per_unit', sa.Float(), default=0.0),
        sa.Column('avg_spoilage_rate', sa.Float(), default=0.0),
        sa.Column('inventory_turnover_rate', sa.Float(), default=0.0),
        sa.Column('recipes_shared_count', sa.Integer(), default=0),
        sa.Column('recipes_sold_count', sa.Integer(), default=0),
        sa.Column('community_rating', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('last_updated', sa.DateTime()),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['most_popular_recipe_id'], ['recipe.id']),
        sa.ForeignKeyConstraint(['most_productive_user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['most_used_container_id'], ['inventory_item.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id')
    )

    # InventoryChangeLog table
    op.create_table('inventory_change_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer()),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('change_category', sa.String(50), nullable=False),
        sa.Column('quantity_change', sa.Float(), nullable=False),
        sa.Column('cost_impact', sa.Float(), default=0.0),
        sa.Column('related_batch_id', sa.Integer()),
        sa.Column('related_lot_id', sa.Integer()),
        sa.Column('reason_code', sa.String(100)),
        sa.Column('notes', sa.Text()),
        sa.Column('item_age_days', sa.Integer()),
        sa.Column('expiration_date', sa.Date()),
        sa.Column('freshness_score', sa.Float()),
        sa.Column('change_date', sa.DateTime()),
        sa.Column('created_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['related_batch_id'], ['batch.id']),
        sa.ForeignKeyConstraint(['related_lot_id'], ['inventory_lot.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for performance
    op.create_index('idx_batch_stats_recipe', 'batch_stats', ['recipe_id'])
    op.create_index('idx_batch_stats_org', 'batch_stats', ['organization_id'])
    op.create_index('idx_recipe_stats_org', 'recipe_stats', ['organization_id'])
    op.create_index('idx_inventory_efficiency_org', 'inventory_efficiency_stats', ['organization_id'])
    op.create_index('idx_change_log_item_date', 'inventory_change_log', ['inventory_item_id', 'change_date'])
    op.create_index('idx_change_log_type_date', 'inventory_change_log', ['change_type', 'change_date'])


def downgrade():
    """Remove comprehensive statistics tables"""
    op.drop_table('inventory_change_log')
    op.drop_table('organization_leaderboard_stats')
    op.drop_table('inventory_efficiency_stats')
    op.drop_table('recipe_stats')
    op.drop_table('batch_stats')