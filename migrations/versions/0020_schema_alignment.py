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


def _rename_column_if_needed(table_name: str, old: str, new: str, type_):
    if not table_exists(table_name):
        return
    if not column_exists(table_name, old):
        return
    if column_exists(table_name, new):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column(old, new_column_name=new, existing_type=type_)


def _ensure_recipe_columns():
    columns = [
        sa.Column('parent_recipe_id', sa.Integer(), nullable=True),
        sa.Column('cloned_from_id', sa.Integer(), nullable=True),
        sa.Column('root_recipe_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='published'),
        sa.Column('sharing_scope', sa.String(length=16), nullable=False, server_default='private'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_for_sale', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sale_price', sa.Numeric(12, 4), nullable=True),
        sa.Column('is_resellable', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('marketplace_status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('marketplace_notes', sa.Text(), nullable=True),
        sa.Column('marketplace_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('marketplace_block_reason', sa.Text(), nullable=True),
        sa.Column('marketplace_violation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('public_description', sa.Text(), nullable=True),
        sa.Column('product_store_url', sa.String(length=512), nullable=True),
        sa.Column('cover_image_path', sa.String(length=255), nullable=True),
        sa.Column('cover_image_url', sa.String(length=512), nullable=True),
        sa.Column('skin_opt_in', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('org_origin_recipe_id', sa.Integer(), nullable=True),
        sa.Column('org_origin_type', sa.String(length=32), nullable=False, server_default='authored'),
        sa.Column('org_origin_source_org_id', sa.Integer(), nullable=True),
        sa.Column('org_origin_source_recipe_id', sa.Integer(), nullable=True),
        sa.Column('org_origin_purchased', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('purchase_count', sa.Integer(), nullable=False, server_default='0'),
    ]
    for column in columns:
        safe_add_column('recipe', column)


def _ensure_recipe_indexes_and_fks():
    safe_create_index('ix_recipe_parent_recipe_id', 'recipe', ['parent_recipe_id'])
    safe_create_index('ix_recipe_cloned_from_id', 'recipe', ['cloned_from_id'])
    safe_create_index('ix_recipe_root_recipe_id', 'recipe', ['root_recipe_id'])
    safe_create_index('ix_recipe_sharing_scope', 'recipe', ['sharing_scope'])
    safe_create_index('ix_recipe_is_public', 'recipe', ['is_public'])
    safe_create_index('ix_recipe_marketplace_status', 'recipe', ['marketplace_status'])
    safe_create_index('ix_recipe_download_count', 'recipe', ['download_count'])
    safe_create_index('ix_recipe_purchase_count', 'recipe', ['purchase_count'])
    safe_create_index('ix_recipe_org_origin_recipe_id', 'recipe', ['org_origin_recipe_id'])
    safe_create_index('ix_recipe_org_origin_type', 'recipe', ['org_origin_type'])
    safe_create_index('ix_recipe_org_origin_source_org_id', 'recipe', ['org_origin_source_org_id'])
    safe_create_index('ix_recipe_org_origin_source_recipe_id', 'recipe', ['org_origin_source_recipe_id'])
    safe_create_index('ix_recipe_org_origin_purchased', 'recipe', ['org_origin_purchased'])

    safe_create_foreign_key('fk_recipe_parent_recipe_id', 'recipe', 'recipe', ['parent_recipe_id'], ['id'])
    safe_create_foreign_key('fk_recipe_cloned_from_id', 'recipe', 'recipe', ['cloned_from_id'], ['id'])
    safe_create_foreign_key('fk_recipe_root_recipe_id', 'recipe', 'recipe', ['root_recipe_id'], ['id'])
    safe_create_foreign_key('fk_recipe_org_origin_recipe_id', 'recipe', 'recipe', ['org_origin_recipe_id'], ['id'])
    safe_create_foreign_key('fk_recipe_org_origin_source_recipe_id', 'recipe', 'recipe', ['org_origin_source_recipe_id'], ['id'])
    safe_create_foreign_key('fk_recipe_org_origin_source_org_id', 'recipe', 'organization', ['org_origin_source_org_id'], ['id'])


def _ensure_recipe_lineage_table():
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


def _standardize_batchbot_indexes():
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


def _drop_inventory_usage_rate():
    safe_drop_column('inventory_item', 'recommended_usage_rate', verbose=False)


def _ensure_organization_recipe_columns():
    additions = [
        sa.Column('recipe_sales_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recipe_library_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recipe_violation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recipe_policy_notes', sa.Text(), nullable=True),
    ]
    for column in additions:
        safe_add_column('organization', column)


def _make_organization_columns_nullable():
    if not table_exists('organization'):
        return
    with op.batch_alter_table('organization') as batch_op:
        if column_exists('organization', 'recipe_sales_blocked'):
            batch_op.alter_column('recipe_sales_blocked', nullable=True, existing_type=sa.Boolean(), existing_server_default=sa.text('false'))
        if column_exists('organization', 'recipe_library_blocked'):
            batch_op.alter_column('recipe_library_blocked', nullable=True, existing_type=sa.Boolean(), existing_server_default=sa.text('false'))
        if column_exists('organization', 'recipe_violation_count'):
            batch_op.alter_column('recipe_violation_count', nullable=True, existing_type=sa.Integer(), existing_server_default=sa.text('0'))


def _update_product_store_url_length():
    if not table_exists('recipe') or not column_exists('recipe', 'product_store_url'):
        return
    with op.batch_alter_table('recipe') as batch_op:
        batch_op.alter_column(
            'product_store_url',
            existing_type=sa.String(length=500),
            type_=sa.String(length=512),
            existing_nullable=True,
        )


def _ensure_addon_fields():
    safe_add_column('addon', sa.Column('batchbot_credit_amount', sa.Integer(), nullable=False, server_default='0'))


def upgrade():
    _standardize_batchbot_indexes()
    _drop_inventory_usage_rate()
    _ensure_organization_recipe_columns()
    _make_organization_columns_nullable()
    _ensure_addon_fields()
    _rename_column_if_needed('global_item', 'aka_names', 'aliases', sa.JSON())
    safe_add_column('global_item', sa.Column('recommended_fragrance_load_pct', sa.String(length=64), nullable=True))
    safe_add_column('global_item', sa.Column('recommended_usage_rate', sa.String(length=64), nullable=True))
    safe_add_column('global_item', sa.Column('is_active_ingredient', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    safe_add_column('global_item', sa.Column('certifications', sa.JSON(), nullable=True))
    safe_add_column('global_item', sa.Column('inci_name', sa.String(length=256), nullable=True))
    safe_add_column('global_item', sa.Column('fatty_acid_profile', sa.JSON(), nullable=True))
    safe_add_column('global_item', sa.Column('brewing_diastatic_power_lintner', sa.Float(), nullable=True))
    safe_add_column('global_item', sa.Column('brewing_potential_sg', sa.Float(), nullable=True))
    safe_add_column('global_item', sa.Column('brewing_color_srm', sa.Float(), nullable=True))
    safe_add_column('global_item', sa.Column('protein_content_pct', sa.Float(), nullable=True))

    safe_add_column('inventory_item', sa.Column('certifications', sa.JSON(), nullable=True))
    safe_add_column('inventory_item', sa.Column('fatty_acid_profile', sa.JSON(), nullable=True))
    safe_add_column('inventory_item', sa.Column('brewing_diastatic_power_lintner', sa.Float(), nullable=True))
    safe_add_column('inventory_item', sa.Column('brewing_potential_sg', sa.Float(), nullable=True))
    safe_add_column('inventory_item', sa.Column('brewing_color_srm', sa.Float(), nullable=True))
    safe_add_column('inventory_item', sa.Column('protein_content_pct', sa.Float(), nullable=True))
    safe_add_column('inventory_item', sa.Column('inci_name', sa.String(length=256), nullable=True))
    safe_add_column('inventory_item', sa.Column('recommended_fragrance_load_pct', sa.String(length=64), nullable=True))

    _rename_column_if_needed('recipe', 'parent_id', 'parent_recipe_id', sa.Integer())
    if column_exists('recipe', 'parent_id') and column_exists('recipe', 'parent_recipe_id'):
        op.execute("UPDATE recipe SET parent_recipe_id = COALESCE(parent_recipe_id, parent_id)")
        safe_drop_column('recipe', 'parent_id', verbose=False)

    _ensure_recipe_columns()
    _ensure_recipe_indexes_and_fks()
    _ensure_recipe_lineage_table()
    _update_product_store_url_length()


def downgrade():
    safe_drop_foreign_key('fk_recipe_org_origin_source_org_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_org_origin_source_recipe_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_org_origin_recipe_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_root_recipe_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_cloned_from_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_parent_recipe_id', 'recipe')

    for index in [
        'ix_recipe_parent_recipe_id',
        'ix_recipe_cloned_from_id',
        'ix_recipe_root_recipe_id',
        'ix_recipe_sharing_scope',
        'ix_recipe_is_public',
        'ix_recipe_marketplace_status',
        'ix_recipe_download_count',
        'ix_recipe_purchase_count',
        'ix_recipe_org_origin_recipe_id',
        'ix_recipe_org_origin_type',
        'ix_recipe_org_origin_source_org_id',
        'ix_recipe_org_origin_source_recipe_id',
        'ix_recipe_org_origin_purchased',
    ]:
        safe_drop_index(index, 'recipe')

    for column in [
        'purchase_count',
        'download_count',
        'org_origin_purchased',
        'org_origin_source_recipe_id',
        'org_origin_source_org_id',
        'org_origin_type',
        'org_origin_recipe_id',
        'skin_opt_in',
        'cover_image_url',
        'cover_image_path',
        'product_store_url',
        'public_description',
        'marketplace_block_reason',
        'marketplace_blocked',
        'marketplace_notes',
        'marketplace_status',
        'is_resellable',
        'sale_price',
        'is_for_sale',
        'is_public',
        'sharing_scope',
        'status',
        'root_recipe_id',
        'cloned_from_id',
        'parent_recipe_id',
    ]:
        safe_drop_column('recipe', column, verbose=False)

    if table_exists('recipe_lineage'):
        safe_drop_index('ix_recipe_lineage_event_type', 'recipe_lineage')
        safe_drop_index('ix_recipe_lineage_source_recipe_id', 'recipe_lineage')
        safe_drop_index('ix_recipe_lineage_recipe_id', 'recipe_lineage')
        op.drop_table('recipe_lineage')

    with op.batch_alter_table('recipe') as batch_op:
        if column_exists('recipe', 'product_store_url'):
            batch_op.alter_column(
                'product_store_url',
                existing_type=sa.String(length=512),
                type_=sa.String(length=500),
                existing_nullable=True,
            )

    with op.batch_alter_table('recipe') as batch_op:
        if not column_exists('recipe', 'parent_id') and column_exists('recipe', 'parent_recipe_id'):
            batch_op.alter_column('parent_recipe_id', new_column_name='parent_id', existing_type=sa.Integer())

    safe_drop_column('inventory_item', 'recommended_fragrance_load_pct', verbose=False)
    safe_drop_column('inventory_item', 'inci_name', verbose=False)
    safe_drop_column('inventory_item', 'protein_content_pct', verbose=False)
    safe_drop_column('inventory_item', 'brewing_color_srm', verbose=False)
    safe_drop_column('inventory_item', 'brewing_potential_sg', verbose=False)
    safe_drop_column('inventory_item', 'brewing_diastatic_power_lintner', verbose=False)
    safe_drop_column('inventory_item', 'fatty_acid_profile', verbose=False)
    safe_drop_column('inventory_item', 'certifications', verbose=False)

    safe_drop_column('global_item', 'protein_content_pct', verbose=False)
    safe_drop_column('global_item', 'brewing_color_srm', verbose=False)
    safe_drop_column('global_item', 'brewing_potential_sg', verbose=False)
    safe_drop_column('global_item', 'brewing_diastatic_power_lintner', verbose=False)
    safe_drop_column('global_item', 'fatty_acid_profile', verbose=False)
    safe_drop_column('global_item', 'inci_name', verbose=False)
    safe_drop_column('global_item', 'certifications', verbose=False)
    safe_drop_column('global_item', 'is_active_ingredient', verbose=False)
    safe_drop_column('global_item', 'recommended_usage_rate', verbose=False)
    safe_drop_column('global_item', 'recommended_fragrance_load_pct', verbose=False)

    if table_exists('organization'):
        with op.batch_alter_table('organization') as batch_op:
            if column_exists('organization', 'recipe_violation_count'):
                batch_op.alter_column('recipe_violation_count', nullable=False, existing_type=sa.Integer(), existing_server_default=sa.text('0'))
            if column_exists('organization', 'recipe_library_blocked'):
                batch_op.alter_column('recipe_library_blocked', nullable=False, existing_type=sa.Boolean(), existing_server_default=sa.text('false'))
            if column_exists('organization', 'recipe_sales_blocked'):
                batch_op.alter_column('recipe_sales_blocked', nullable=False, existing_type=sa.Boolean(), existing_server_default=sa.text('false'))

    safe_drop_column('organization', 'recipe_policy_notes', verbose=False)
    safe_drop_column('organization', 'recipe_violation_count', verbose=False)
    safe_drop_column('organization', 'recipe_library_blocked', verbose=False)
    safe_drop_column('organization', 'recipe_sales_blocked', verbose=False)

    safe_drop_column('addon', 'batchbot_credit_amount', verbose=False)

    if index_exists('batchbot_usage', 'ix_batchbot_usage_organization_id'):
        with op.batch_alter_table('batchbot_usage') as batch_op:
            batch_op.drop_index('ix_batchbot_usage_organization_id')
            batch_op.create_index('ix_batchbot_usage_org_id', ['organization_id'], unique=False)
    if index_exists('batchbot_credit_bundle', 'ix_batchbot_credit_bundle_organization_id'):
        with op.batch_alter_table('batchbot_credit_bundle') as batch_op:
            batch_op.drop_index('ix_batchbot_credit_bundle_organization_id')
            batch_op.create_index('ix_batchbot_credit_bundle_org_id', ['organization_id'], unique=False)
