"""0011 recipe marketplace

Revision ID: 0011_recipe_marketplace
Revises: 0010_recipe_status_drafts
Create Date: 2025-11-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    safe_add_column,
    safe_drop_column,
    table_exists,
    index_exists,
)

# revision identifiers, used by Alembic.
revision = '0011_recipe_marketplace'
down_revision = '0010_recipe_status_drafts'
branch_labels = None
depends_on = None


def upgrade():
    # Recipe product groups
    if not table_exists('recipe_product_group'):
        op.create_table(
            'recipe_product_group',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=80), nullable=False, unique=True),
            sa.Column('slug', sa.String(length=80), nullable=False, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('icon', sa.String(length=64), nullable=True),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    # Moderation events
    if not table_exists('recipe_moderation_event'):
        op.create_table(
            'recipe_moderation_event',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('recipe.id'), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
            sa.Column('moderated_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
            sa.Column('action', sa.String(length=64), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('violation_delta', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('ix_recipe_moderation_recipe_id', 'recipe_moderation_event', ['recipe_id'])
        op.create_index('ix_recipe_moderation_org_id', 'recipe_moderation_event', ['organization_id'])

    # Recipe table enhancements
    safe_add_column('recipe', sa.Column('sharing_scope', sa.String(length=16), nullable=False, server_default='private'))
    safe_add_column('recipe', sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('recipe', sa.Column('is_for_sale', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('recipe', sa.Column('sale_price', sa.Numeric(12, 4), nullable=True))
    safe_add_column('recipe', sa.Column('marketplace_status', sa.String(length=32), nullable=False, server_default='draft'))
    safe_add_column('recipe', sa.Column('marketplace_notes', sa.Text(), nullable=True))
    safe_add_column('recipe', sa.Column('marketplace_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('recipe', sa.Column('marketplace_block_reason', sa.Text(), nullable=True))
    safe_add_column('recipe', sa.Column('marketplace_violation_count', sa.Integer(), nullable=False, server_default='0'))
    safe_add_column('recipe', sa.Column('shopify_product_url', sa.String(length=512), nullable=True))
    safe_add_column('recipe', sa.Column('product_group_id', sa.Integer(), nullable=True))
    safe_add_column('recipe', sa.Column('cover_image_path', sa.String(length=255), nullable=True))
    safe_add_column('recipe', sa.Column('cover_image_url', sa.String(length=512), nullable=True))
    safe_add_column('recipe', sa.Column('skin_opt_in', sa.Boolean(), nullable=False, server_default=sa.text('true')))

    if table_exists('recipe'):
        try:
            op.create_foreign_key(
                'fk_recipe_product_group',
                source_table='recipe',
                referent_table='recipe_product_group',
                local_cols=['product_group_id'],
                remote_cols=['id'],
            )
        except Exception:
            pass

        if not index_exists('recipe', 'ix_recipe_sharing_scope'):
            op.create_index('ix_recipe_sharing_scope', 'recipe', ['sharing_scope'])
        if not index_exists('recipe', 'ix_recipe_is_public'):
            op.create_index('ix_recipe_is_public', 'recipe', ['is_public'])
        if not index_exists('recipe', 'ix_recipe_product_group_id'):
            op.create_index('ix_recipe_product_group_id', 'recipe', ['product_group_id'])
        if not index_exists('recipe', 'ix_recipe_marketplace_status'):
            op.create_index('ix_recipe_marketplace_status', 'recipe', ['marketplace_status'])

    # Organization level governance fields
    safe_add_column('organization', sa.Column('recipe_sales_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('organization', sa.Column('recipe_library_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('organization', sa.Column('recipe_violation_count', sa.Integer(), nullable=False, server_default='0'))
    safe_add_column('organization', sa.Column('recipe_policy_notes', sa.Text(), nullable=True))


def downgrade():
    # Organization columns
    safe_drop_column('organization', 'recipe_policy_notes')
    safe_drop_column('organization', 'recipe_violation_count')
    safe_drop_column('organization', 'recipe_library_blocked')
    safe_drop_column('organization', 'recipe_sales_blocked')

    # Recipe indexes and FK
    if index_exists('recipe', 'ix_recipe_marketplace_status'):
        op.drop_index('ix_recipe_marketplace_status', table_name='recipe')
    if index_exists('recipe', 'ix_recipe_product_group_id'):
        op.drop_index('ix_recipe_product_group_id', table_name='recipe')
    if index_exists('recipe', 'ix_recipe_is_public'):
        op.drop_index('ix_recipe_is_public', table_name='recipe')
    if index_exists('recipe', 'ix_recipe_sharing_scope'):
        op.drop_index('ix_recipe_sharing_scope', table_name='recipe')

    try:
        op.drop_constraint('fk_recipe_product_group', 'recipe', type_='foreignkey')
    except Exception:
        pass

    # Recipe columns
    safe_drop_column('recipe', 'skin_opt_in')
    safe_drop_column('recipe', 'cover_image_url')
    safe_drop_column('recipe', 'cover_image_path')
    safe_drop_column('recipe', 'product_group_id')
    safe_drop_column('recipe', 'shopify_product_url')
    safe_drop_column('recipe', 'marketplace_violation_count')
    safe_drop_column('recipe', 'marketplace_block_reason')
    safe_drop_column('recipe', 'marketplace_blocked')
    safe_drop_column('recipe', 'marketplace_notes')
    safe_drop_column('recipe', 'marketplace_status')
    safe_drop_column('recipe', 'sale_price')
    safe_drop_column('recipe', 'is_for_sale')
    safe_drop_column('recipe', 'is_public')
    safe_drop_column('recipe', 'sharing_scope')

    # Moderation table/index
    try:
        op.drop_index('ix_recipe_moderation_org_id', table_name='recipe_moderation_event')
    except Exception:
        pass
    try:
        op.drop_index('ix_recipe_moderation_recipe_id', table_name='recipe_moderation_event')
    except Exception:
        pass
    if table_exists('recipe_moderation_event'):
        op.drop_table('recipe_moderation_event')

    # Product group table
    if table_exists('recipe_product_group'):
        op.drop_table('recipe_product_group')
