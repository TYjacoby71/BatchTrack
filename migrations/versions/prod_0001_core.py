"""Production bootstrap 0001 - core identity, ACL, tiers, and taxonomy

Revision ID: prod_0001_core
Revises: 
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'prod_0001_core'
down_revision = None
branch_labels = ('production_bootstrap',)
depends_on = None


def upgrade():
    # 1) Subscription tiers (root for Organization FK)
    op.create_table(
        'subscription_tier',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tier_type', sa.String(length=32), nullable=False, server_default='monthly'),
        sa.Column('user_limit', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_users', sa.Integer(), nullable=True),
        sa.Column('max_recipes', sa.Integer(), nullable=True),
        sa.Column('max_batches', sa.Integer(), nullable=True),
        sa.Column('max_products', sa.Integer(), nullable=True),
        sa.Column('max_batchbot_requests', sa.Integer(), nullable=True),
        sa.Column('max_monthly_batches', sa.Integer(), nullable=True),
        sa.Column('data_retention_days', sa.Integer(), nullable=True),
        sa.Column('retention_notice_days', sa.Integer(), nullable=True),
        sa.Column('storage_addon_retention_days', sa.Integer(), nullable=True),
        sa.Column('is_customer_facing', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('billing_provider', sa.String(length=32), nullable=False, server_default='exempt'),
        sa.Column('stripe_lookup_key', sa.String(length=128), nullable=True),
        sa.Column('stripe_storage_lookup_key', sa.String(length=128), nullable=True),
        sa.Column('whop_product_key', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('stripe_lookup_key', name='uq_subscription_tier_stripe_lookup_key'),
        sa.UniqueConstraint('stripe_storage_lookup_key', name='uq_subscription_tier_stripe_storage_lookup_key'),
        sa.UniqueConstraint('whop_product_key', name='uq_subscription_tier_whop_product_key'),
    )

    # 2) Organization (references subscription_tier)
    op.create_table(
        'organization',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('contact_email', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('signup_source', sa.String(length=64), nullable=True),
        sa.Column('promo_code', sa.String(length=32), nullable=True),
        sa.Column('referral_code', sa.String(length=32), nullable=True),
        sa.Column('subscription_tier_id', sa.Integer(), nullable=True),
        sa.Column('whop_license_key', sa.String(length=255), nullable=True),
        sa.Column('whop_product_tier', sa.String(length=32), nullable=True),
        sa.Column('whop_verified', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('stripe_subscription_id', sa.String(length=128), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('billing_info', sa.Text(), nullable=True),
        sa.Column('next_billing_date', sa.Date(), nullable=True),
        sa.Column('subscription_status', sa.String(length=32), nullable=True, server_default='inactive'),
        sa.Column('billing_status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('last_online_sync', sa.DateTime(), nullable=True),
        sa.Column('offline_tier_cache', sa.JSON(), nullable=True),
        sa.Column('inventory_cost_method', sa.String(length=16), nullable=True),
        sa.Column('inventory_cost_method_changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['subscription_tier_id'], ['subscription_tier.id'], name='fk_organization_subscription_tier_id', ondelete='SET NULL'),
    )

    # 3) User
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=64), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True, server_default=''),
        sa.Column('first_name', sa.String(length=64), nullable=True),
        sa.Column('last_name', sa.String(length=64), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('user_type', sa.String(length=32), nullable=True, server_default='customer'),
        sa.Column('is_organization_owner', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('email_verification_token', sa.String(length=255), nullable=True),
        sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True),
        sa.Column('oauth_provider', sa.String(length=50), nullable=True),
        sa.Column('oauth_provider_id', sa.String(length=255), nullable=True),
        sa.Column('password_reset_token', sa.String(length=255), nullable=True),
        sa.Column('password_reset_sent_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['deleted_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    # 4) Permissions & Roles, and associations
    op.create_table(
        'permission',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'role',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('is_system_role', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('name', 'organization_id', name='unique_role_name_org'),
    )

    op.create_table(
        'role_permission',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['role.id']),
        sa.ForeignKeyConstraint(['permission_id'], ['permission.id']),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    # Subscription tier <-> permission association
    op.create_table(
        'subscription_tier_permission',
        sa.Column('tier_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tier_id'], ['subscription_tier.id']),
        sa.ForeignKeyConstraint(['permission_id'], ['permission.id']),
        sa.PrimaryKeyConstraint('tier_id', 'permission_id')
    )

    # 5) Developer roles & permissions
    op.create_table(
        'developer_permission',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'developer_role',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=True, server_default='developer'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'developer_role_permission',
        sa.Column('developer_role_id', sa.Integer(), nullable=False),
        sa.Column('developer_permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['developer_role_id'], ['developer_role.id']),
        sa.ForeignKeyConstraint(['developer_permission_id'], ['developer_permission.id']),
        sa.PrimaryKeyConstraint('developer_role_id', 'developer_permission_id')
    )

    # 6) User role assignments
    op.create_table(
        'user_role_assignment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('developer_role_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['role_id'], ['role.id']),
        sa.ForeignKeyConstraint(['developer_role_id'], ['developer_role.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['assigned_by'], ['user.id']),
    )

    # 7) User preferences
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('max_dashboard_alerts', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('show_expiration_alerts', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('show_timer_alerts', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('show_low_stock_alerts', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('show_batch_alerts', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('show_fault_alerts', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('show_alert_badges', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('dashboard_layout', sa.String(length=32), nullable=True, server_default='standard'),
        sa.Column('compact_view', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('show_quick_actions', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('timezone', sa.String(length=64), nullable=True, server_default='America/New_York'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    # 8) Units and conversions (no conversion mapping FKs to inventory at this stage)
    op.create_table(
        'unit',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=True),
        sa.Column('unit_type', sa.String(length=32), nullable=False),
        sa.Column('conversion_factor', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('base_unit', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('is_custom', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('is_mapped', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('name', 'organization_id', name='_unit_name_org_uc'),
    )

    op.create_table(
        'custom_unit_mapping',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('from_unit', sa.String(length=64), nullable=False),
        sa.Column('to_unit', sa.String(length=64), nullable=False),
        sa.Column('conversion_factor', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'conversion_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('from_unit', sa.String(length=32), nullable=False),
        sa.Column('to_unit', sa.String(length=32), nullable=False),
        sa.Column('result', sa.Float(), nullable=False),
        sa.Column('conversion_type', sa.String(length=64), nullable=False),
        sa.Column('ingredient_name', sa.String(length=128), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    # 9) Categories & tags
    op.create_table(
        'ingredient_category',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=7), nullable=True, server_default='#6c757d'),
        sa.Column('default_density', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('is_global_category', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )

    op.create_table(
        'inventory_category',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('item_type', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('name', 'item_type', 'organization_id', name='_invcat_name_type_org_uc'),
    )

    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=True, server_default='#6c757d'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('name', 'organization_id', name='_tag_name_org_uc'),
    )

    # 10) Stripe events (idempotency log)
    op.create_table(
        'stripe_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True, server_default='received'),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    op.create_index('ix_stripe_event_event_id', 'stripe_event', ['event_id'], unique=True)


def downgrade():
    # Reverse creation order
    op.drop_index('ix_stripe_event_event_id', table_name='stripe_event')
    op.drop_table('stripe_event')
    op.drop_table('tag')
    op.drop_table('inventory_category')
    op.drop_table('ingredient_category')
    op.drop_table('conversion_log')
    op.drop_table('custom_unit_mapping')
    op.drop_table('unit')
    op.drop_table('user_preferences')
    op.drop_table('user_role_assignment')
    op.drop_table('developer_role_permission')
    op.drop_table('developer_role')
    op.drop_table('developer_permission')
    op.drop_table('subscription_tier_permission')
    op.drop_table('role_permission')
    op.drop_table('role')
    op.drop_table('permission')
    op.drop_table('user')
    op.drop_table('organization')
    op.drop_table('subscription_tier')

