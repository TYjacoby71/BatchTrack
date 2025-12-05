"""0020 schema alignment - BatchTrack

Revision ID: 0020_schema_alignment
Revises: 0019
Create Date: 2025-12-05 19:09:07.654429

"""
from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    column_exists,
    index_exists,
    safe_add_column,
    safe_create_foreign_key,
    safe_create_index,
    safe_drop_column,
    safe_drop_foreign_key,
    safe_drop_index,
    table_exists,
)


revision = '0020_schema_alignment'
down_revision = '0019'
branch_labels = None
depends_on = None


def _rename_column_if_needed(table_name: str, old: str, new: str, column_type) -> None:
    if not table_exists(table_name):
        return
    if not column_exists(table_name, old):
        return
    if column_exists(table_name, new):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column(old, new_column_name=new, existing_type=column_type)


def _standardize_batchbot_indexes() -> None:
    if index_exists('batchbot_credit_bundle', 'ix_batchbot_credit_bundle_addon_id'):
        with op.batch_alter_table('batchbot_credit_bundle') as batch_op:
            batch_op.drop_index('ix_batchbot_credit_bundle_addon_id')
    if index_exists('batchbot_credit_bundle', 'ix_batchbot_credit_bundle_org_id'):
        with op.batch_alter_table('batchbot_credit_bundle') as batch_op:
            batch_op.drop_index('ix_batchbot_credit_bundle_org_id')
    if not index_exists('batchbot_credit_bundle', 'ix_batchbot_credit_bundle_organization_id'):
        with op.batch_alter_table('batchbot_credit_bundle') as batch_op:
            batch_op.create_index(batch_op.f('ix_batchbot_credit_bundle_organization_id'), ['organization_id'], unique=False)

    if index_exists('batchbot_usage', 'ix_batchbot_usage_org_id'):
        with op.batch_alter_table('batchbot_usage') as batch_op:
            batch_op.drop_index('ix_batchbot_usage_org_id')
    if not index_exists('batchbot_usage', 'ix_batchbot_usage_organization_id'):
        with op.batch_alter_table('batchbot_usage') as batch_op:
            batch_op.create_index(batch_op.f('ix_batchbot_usage_organization_id'), ['organization_id'], unique=False)


def _drop_inventory_usage_rate() -> None:
    safe_drop_column('inventory_item', 'recommended_usage_rate', verbose=False)


def _ensure_organization_recipe_columns() -> None:
    additions = [
        sa.Column('recipe_sales_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recipe_library_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recipe_violation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recipe_policy_notes', sa.Text(), nullable=True),
    ]
    for column in additions:
        safe_add_column('organization', column)


def _make_organization_columns_nullable() -> None:
    if not table_exists('organization'):
        return
    with op.batch_alter_table('organization') as batch_op:
        if column_exists('organization', 'recipe_sales_blocked'):
            batch_op.alter_column('recipe_sales_blocked', nullable=True, existing_type=sa.Boolean(), existing_server_default=sa.text('false'))
        if column_exists('organization', 'recipe_library_blocked'):
            batch_op.alter_column('recipe_library_blocked', nullable=True, existing_type=sa.Boolean(), existing_server_default=sa.text('false'))
        if column_exists('organization', 'recipe_violation_count'):
            batch_op.alter_column('recipe_violation_count', nullable=True, existing_type=sa.Integer(), existing_server_default=sa.text('0'))


def _ensure_addon_fields() -> None:
    safe_add_column('addon', sa.Column('batchbot_credit_amount', sa.Integer(), nullable=False, server_default='0'))


def _remove_sharing_scope_columns() -> None:
    # Keep sharing_scope and marketplace_notes columns - they're still used
    # safe_drop_index('ix_recipe_sharing_scope', 'recipe')
    for column in (
        'marketplace_blocked',
        'marketplace_block_reason',
    ):
        safe_drop_column('recipe', column, verbose=False)


def _replace_is_resellable() -> None:
    if not column_exists('recipe', 'is_sellable'):
        safe_add_column('recipe', sa.Column('is_sellable', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    if column_exists('recipe', 'is_resellable'):
        op.execute("UPDATE recipe SET is_sellable = COALESCE(is_resellable, true)")
        safe_drop_column('recipe', 'is_resellable', verbose=False)


def _drop_legacy_origin_columns() -> None:
    # Keep the org origin columns and indexes - they're still used in the codebase
    # Only drop the unused source recipe id column
    safe_drop_column('recipe', 'org_origin_source_recipe_id', verbose=False)


def _ensure_recipe_marketplace_columns() -> None:
    columns = [
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_for_sale', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sale_price', sa.Numeric(12, 4), nullable=True),
        sa.Column('marketplace_status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('marketplace_violation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('public_description', sa.Text(), nullable=True),
        sa.Column('product_store_url', sa.String(length=512), nullable=True),
        sa.Column('cover_image_path', sa.String(length=255), nullable=True),
        sa.Column('cover_image_url', sa.String(length=512), nullable=True),
        sa.Column('skin_opt_in', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('origin_recipe_id', sa.Integer(), nullable=True),
        sa.Column('origin_organization_id', sa.Integer(), nullable=True),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('purchase_count', sa.Integer(), nullable=False, server_default='0'),
    ]
    for column in columns:
        safe_add_column('recipe', column)


def _ensure_recipe_indexes_and_fks() -> None:
    for index_name, column in (
        ('ix_recipe_is_public', 'is_public'),
        ('ix_recipe_is_for_sale', 'is_for_sale'),
        ('ix_recipe_is_sellable', 'is_sellable'),
        ('ix_recipe_marketplace_status', 'marketplace_status'),
        ('ix_recipe_origin_recipe_id', 'origin_recipe_id'),
        ('ix_recipe_origin_organization_id', 'origin_organization_id'),
        ('ix_recipe_download_count', 'download_count'),
        ('ix_recipe_purchase_count', 'purchase_count'),
    ):
        safe_create_index(index_name, 'recipe', [column])

    # Check for existing foreign keys from migration 0013 before creating
    from migrations.postgres_helpers import constraint_exists
    
    if not constraint_exists('recipe', 'fk_recipe_origin_recipe_id'):
        safe_create_foreign_key('fk_recipe_origin_recipe_id', 'recipe', 'recipe', ['origin_recipe_id'], ['id'])
    
    if not constraint_exists('recipe', 'fk_recipe_origin_org_id'):
        safe_create_foreign_key('fk_recipe_origin_org_id', 'recipe', 'organization', ['origin_organization_id'], ['id'])


def _ensure_recipe_lineage_table() -> None:
    if table_exists('recipe_lineage'):
        return
    op.create_table(
        'recipe_lineage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('recipe.id'), nullable=False),
        sa.Column('source_recipe_id', sa.Integer(), sa.ForeignKey('recipe.id'), nullable=True),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    safe_create_index('ix_recipe_lineage_recipe_id', 'recipe_lineage', ['recipe_id'])
    safe_create_index('ix_recipe_lineage_source_recipe_id', 'recipe_lineage', ['source_recipe_id'])
    safe_create_index('ix_recipe_lineage_event_type', 'recipe_lineage', ['event_type'])


def _update_product_store_url_length() -> None:
    if not table_exists('recipe') or not column_exists('recipe', 'product_store_url'):
        return
    with op.batch_alter_table('recipe') as batch_op:
        batch_op.alter_column(
            'product_store_url',
            existing_type=sa.String(length=500),
            type_=sa.String(length=512),
            existing_nullable=True,
        )


def upgrade():
    _standardize_batchbot_indexes()
    _drop_inventory_usage_rate()
    _ensure_organization_recipe_columns()
    _make_organization_columns_nullable()
    _ensure_addon_fields()

    _rename_column_if_needed('recipe', 'parent_id', 'parent_recipe_id', sa.Integer())
    _rename_column_if_needed('recipe', 'org_origin_recipe_id', 'origin_recipe_id', sa.Integer())
    _rename_column_if_needed('recipe', 'org_origin_source_org_id', 'origin_organization_id', sa.Integer())

    _replace_is_resellable()
    _drop_legacy_origin_columns()
    _remove_sharing_scope_columns()

    _ensure_recipe_marketplace_columns()
    _ensure_recipe_indexes_and_fks()
    _ensure_recipe_lineage_table()
    _update_product_store_url_length()


def downgrade():
    for fk in (
        'fk_recipe_origin_org_id',
        'fk_recipe_origin_recipe_id',
    ):
        safe_drop_foreign_key(fk, 'recipe')

    for index_name in (
        'ix_recipe_is_public',
        'ix_recipe_is_for_sale',
        'ix_recipe_is_sellable',
        'ix_recipe_marketplace_status',
        'ix_recipe_origin_recipe_id',
        'ix_recipe_origin_organization_id',
        'ix_recipe_download_count',
        'ix_recipe_purchase_count',
    ):
        safe_drop_index(index_name, 'recipe')

    for column in (
        'purchase_count',
        'download_count',
        'origin_organization_id',
        'origin_recipe_id',
        'skin_opt_in',
        'cover_image_url',
        'cover_image_path',
        'product_store_url',
        'public_description',
        'marketplace_violation_count',
        'marketplace_status',
        'sale_price',
        'is_for_sale',
        'is_public',
    ):
        safe_drop_column('recipe', column, verbose=False)

    if column_exists('recipe', 'is_sellable') and not column_exists('recipe', 'is_resellable'):
        safe_add_column('recipe', sa.Column('is_resellable', sa.Boolean(), nullable=False, server_default=sa.text('true')))
        op.execute("UPDATE recipe SET is_resellable = COALESCE(is_sellable, true)")
    safe_drop_column('recipe', 'is_sellable', verbose=False)

    for column in (
        'recipe_policy_notes',
        'recipe_violation_count',
        'recipe_library_blocked',
        'recipe_sales_blocked',
    ):
        safe_drop_column('organization', column, verbose=False)

    safe_drop_column('addon', 'batchbot_credit_amount', verbose=False)

    if table_exists('recipe_lineage'):
        safe_drop_index('ix_recipe_lineage_event_type', 'recipe_lineage')
        safe_drop_index('ix_recipe_lineage_source_recipe_id', 'recipe_lineage')
        safe_drop_index('ix_recipe_lineage_recipe_id', 'recipe_lineage')
        op.drop_table('recipe_lineage')

    # Restore only the columns we actually dropped
    safe_add_column('recipe', sa.Column('marketplace_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('recipe', sa.Column('marketplace_block_reason', sa.Text(), nullable=True))
    safe_add_column('recipe', sa.Column('org_origin_source_recipe_id', sa.Integer(), nullable=True))

    safe_create_foreign_key('fk_recipe_origin_source_recipe_id', 'recipe', 'recipe', ['org_origin_source_recipe_id'], ['id'])