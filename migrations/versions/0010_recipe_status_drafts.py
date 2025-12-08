"""0010 recipe status, marketplace, and lineage baseline

Revision ID: 0010_recipe_status_drafts
Revises: 0009_drop_billing_snapshots
Create Date: 2025-11-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from migrations.postgres_helpers import (
    column_exists,
    constraint_exists,
    index_exists,
    is_sqlite,
    safe_add_column,
    safe_drop_column,
    safe_create_foreign_key,
    safe_drop_foreign_key,
    safe_create_index,
    safe_drop_index,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = '0010_recipe_status_drafts'
down_revision = '0009_drop_billing_snapshots'
branch_labels = None
depends_on = None

BATCHTRACK_ORG_ID = 1
LEGACY_BATCH_LABEL_CONSTRAINT = 'batch_label_code_key'
SCOPED_BATCH_LABEL_CONSTRAINT = 'uq_batch_org_label'


def upgrade():
    _add_recipe_status_and_marketplace()
    _add_recipe_moderation_table()
    _add_organization_recipe_controls()
    _ensure_batchbot_tables()
    _ensure_batch_label_scope_constraint()
    _ensure_unit_indexes()
    _ensure_hot_path_indexes()


def downgrade():
    _drop_hot_path_indexes()
    _drop_unit_indexes()
    _revert_batch_label_scope_constraint()
    _drop_batchbot_tables()
    _drop_organization_recipe_controls()
    _drop_recipe_moderation_table()
    _drop_recipe_marketplace_columns()


def _add_recipe_status_and_marketplace():
    recipe_columns = [
        sa.Column('status', sa.String(length=16), nullable=False, server_default='published'),
        sa.Column('sharing_scope', sa.String(length=16), nullable=False, server_default='private'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_for_sale', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sale_price', sa.Numeric(12, 4), nullable=True),
        sa.Column('marketplace_status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('marketplace_notes', sa.Text(), nullable=True),
        sa.Column('marketplace_violation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shopify_product_url', sa.String(length=512), nullable=True),
        sa.Column('product_store_url', sa.String(length=512), nullable=True),
        sa.Column('cover_image_path', sa.String(length=255), nullable=True),
        sa.Column('cover_image_url', sa.String(length=512), nullable=True),
        sa.Column('skin_opt_in', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('public_description', sa.Text(), nullable=True),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('purchase_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('org_origin_recipe_id', sa.Integer(), nullable=True),
        sa.Column('org_origin_type', sa.String(length=32), nullable=False, server_default='authored'),
        sa.Column('org_origin_source_org_id', sa.Integer(), nullable=True),
        sa.Column('org_origin_source_recipe_id', sa.Integer(), nullable=True),
        sa.Column('org_origin_purchased', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('origin_recipe_id', sa.Integer(), nullable=True),
        sa.Column('origin_organization_id', sa.Integer(), nullable=True),
        sa.Column('is_sellable', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    ]

    for column in recipe_columns:
        safe_add_column('recipe', column)

    recipe_indexes = [
        ('ix_recipe_sharing_scope', ['sharing_scope']),
        ('ix_recipe_is_public', ['is_public']),
        ('ix_recipe_is_for_sale', ['is_for_sale']),
        ('ix_recipe_marketplace_status', ['marketplace_status']),
        ('ix_recipe_is_sellable', ['is_sellable']),
        ('ix_recipe_product_store_url', ['product_store_url']),
        ('ix_recipe_origin_recipe_id', ['origin_recipe_id']),
        ('ix_recipe_origin_organization_id', ['origin_organization_id']),
        ('ix_recipe_download_count', ['download_count']),
        ('ix_recipe_purchase_count', ['purchase_count']),
        ('ix_recipe_org_origin_recipe_id', ['org_origin_recipe_id']),
        ('ix_recipe_org_origin_type', ['org_origin_type']),
        ('ix_recipe_org_origin_source_org_id', ['org_origin_source_org_id']),
        ('ix_recipe_org_origin_purchased', ['org_origin_purchased']),
    ]

    for index_name, columns in recipe_indexes:
        safe_create_index(index_name, 'recipe', columns)

    recipe_foreign_keys = [
        ('fk_recipe_org_origin_recipe_id', 'recipe', ['org_origin_recipe_id'], 'recipe', ['id']),
        ('fk_recipe_org_origin_source_recipe_id', 'recipe', ['org_origin_source_recipe_id'], 'recipe', ['id']),
        ('fk_recipe_org_origin_source_org_id', 'recipe', ['org_origin_source_org_id'], 'organization', ['id']),
        ('fk_recipe_origin_recipe_id', 'recipe', ['origin_recipe_id'], 'recipe', ['id']),
        ('fk_recipe_origin_org_id', 'recipe', ['origin_organization_id'], 'organization', ['id']),
    ]

    for fk_name, source_table, local_cols, target_table, remote_cols in recipe_foreign_keys:
        safe_create_foreign_key(fk_name, source_table, target_table, local_cols, remote_cols)

    if table_exists('recipe'):
        op.execute(sa.text("UPDATE recipe SET status = COALESCE(status, 'published')"))
        op.execute(sa.text("UPDATE recipe SET sharing_scope = 'private' WHERE sharing_scope IS NULL OR sharing_scope = ''"))
        op.execute(sa.text("UPDATE recipe SET marketplace_status = 'draft' WHERE marketplace_status IS NULL OR marketplace_status = ''"))
        op.execute(sa.text("UPDATE recipe SET marketplace_violation_count = 0 WHERE marketplace_violation_count IS NULL"))
        op.execute(sa.text("UPDATE recipe SET download_count = 0 WHERE download_count IS NULL"))
        op.execute(sa.text("UPDATE recipe SET purchase_count = 0 WHERE purchase_count IS NULL"))
        op.execute(sa.text("UPDATE recipe SET skin_opt_in = COALESCE(skin_opt_in, TRUE)"))
        op.execute(sa.text("UPDATE recipe SET org_origin_purchased = COALESCE(org_origin_purchased, FALSE)"))
        op.execute(sa.text("UPDATE recipe SET org_origin_recipe_id = COALESCE(org_origin_recipe_id, COALESCE(root_recipe_id, id))"))
        op.execute(
            sa.text(
                """
                UPDATE recipe
                SET org_origin_type = CASE
                    WHEN organization_id = :batchtrack_org THEN 'batchtrack_native'
                    ELSE 'authored'
                END
                WHERE org_origin_type IS NULL OR org_origin_type = ''
                """
            ),
            {'batchtrack_org': BATCHTRACK_ORG_ID},
        )
        op.execute(
            sa.text(
                """
                UPDATE recipe
                SET is_sellable = CASE
                    WHEN org_origin_purchased IS TRUE THEN FALSE
                    ELSE TRUE
                END
                WHERE is_sellable IS NULL
                """
            )
        )


def _add_recipe_moderation_table():
    if table_exists('recipe_moderation_event'):
        return
    op.create_table(
        'recipe_moderation_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('recipe.id'), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
        sa.Column('moderated_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('violation_delta', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    safe_create_index('ix_recipe_moderation_recipe_id', 'recipe_moderation_event', ['recipe_id'])
    safe_create_index('ix_recipe_moderation_org_id', 'recipe_moderation_event', ['organization_id'])


def _drop_recipe_moderation_table():
    safe_drop_index('ix_recipe_moderation_org_id', 'recipe_moderation_event')
    safe_drop_index('ix_recipe_moderation_recipe_id', 'recipe_moderation_event')
    if table_exists('recipe_moderation_event'):
        op.drop_table('recipe_moderation_event')


def _add_organization_recipe_controls():
    org_columns = [
        sa.Column('recipe_sales_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recipe_library_blocked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('recipe_violation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recipe_policy_notes', sa.Text(), nullable=True),
    ]
    for column in org_columns:
        safe_add_column('organization', column)


def _drop_organization_recipe_controls():
    for column_name in ['recipe_policy_notes', 'recipe_violation_count', 'recipe_library_blocked', 'recipe_sales_blocked']:
        safe_drop_column('organization', column_name, verbose=False)


def _ensure_batchbot_tables():
    if not table_exists('batchbot_usage'):
        op.create_table(
            'batchbot_usage',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
            sa.Column('window_start', sa.Date(), nullable=False),
            sa.Column('window_end', sa.Date(), nullable=False),
            sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_request_at', sa.DateTime(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('organization_id', 'window_start', name='uq_batchbot_usage_org_window'),
        )
    safe_create_index('ix_batchbot_usage_organization_id', 'batchbot_usage', ['organization_id'])
    safe_create_index('ix_batchbot_usage_user_id', 'batchbot_usage', ['user_id'])
    safe_create_index('ix_batchbot_usage_window_start', 'batchbot_usage', ['window_start'])

    if not table_exists('batchbot_credit_bundle'):
        op.create_table(
            'batchbot_credit_bundle',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=False),
            sa.Column('addon_id', sa.Integer(), sa.ForeignKey('addon.id'), nullable=True),
            sa.Column('source', sa.String(length=64), nullable=False, server_default='manual'),
            sa.Column('reference', sa.String(length=128), nullable=True),
            sa.Column('purchased_requests', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('remaining_requests', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    safe_create_index('ix_batchbot_credit_bundle_organization_id', 'batchbot_credit_bundle', ['organization_id'])
    safe_create_index('ix_batchbot_credit_bundle_addon_id', 'batchbot_credit_bundle', ['addon_id'])

    safe_add_column('addon', sa.Column('batchbot_credit_amount', sa.Integer(), nullable=False, server_default='0'))


def _drop_batchbot_tables():
    safe_drop_index('ix_batchbot_credit_bundle_addon_id', 'batchbot_credit_bundle')
    safe_drop_index('ix_batchbot_credit_bundle_organization_id', 'batchbot_credit_bundle')
    if table_exists('batchbot_credit_bundle'):
        op.drop_table('batchbot_credit_bundle')

    safe_drop_index('ix_batchbot_usage_window_start', 'batchbot_usage')
    safe_drop_index('ix_batchbot_usage_user_id', 'batchbot_usage')
    safe_drop_index('ix_batchbot_usage_organization_id', 'batchbot_usage')
    if table_exists('batchbot_usage'):
        op.drop_table('batchbot_usage')

    safe_drop_column('addon', 'batchbot_credit_amount', verbose=False)


def _ensure_batch_label_scope_constraint():
    if not table_exists('batch'):
        return
    if is_sqlite():
        with op.batch_alter_table('batch', recreate='always') as batch_op:
            _drop_sqlite_unique(batch_op, LEGACY_BATCH_LABEL_CONSTRAINT, ['label_code'])
            existing = constraint_exists('batch', SCOPED_BATCH_LABEL_CONSTRAINT)
            if not existing:
                batch_op.create_unique_constraint(SCOPED_BATCH_LABEL_CONSTRAINT, ['organization_id', 'label_code'])
    else:
        if constraint_exists('batch', LEGACY_BATCH_LABEL_CONSTRAINT):
            op.drop_constraint(LEGACY_BATCH_LABEL_CONSTRAINT, 'batch', type_='unique')
        if not constraint_exists('batch', SCOPED_BATCH_LABEL_CONSTRAINT):
            op.create_unique_constraint(SCOPED_BATCH_LABEL_CONSTRAINT, 'batch', ['organization_id', 'label_code'])


def _revert_batch_label_scope_constraint():
    if not table_exists('batch'):
        return
    if is_sqlite():
        with op.batch_alter_table('batch', recreate='always') as batch_op:
            _drop_sqlite_unique(batch_op, SCOPED_BATCH_LABEL_CONSTRAINT, ['organization_id', 'label_code'])
            _dedupe_legacy_label_codes()
            batch_op.create_unique_constraint(LEGACY_BATCH_LABEL_CONSTRAINT, ['label_code'])
    else:
        if constraint_exists('batch', SCOPED_BATCH_LABEL_CONSTRAINT):
            op.drop_constraint(SCOPED_BATCH_LABEL_CONSTRAINT, 'batch', type_='unique')
        _dedupe_legacy_label_codes()
        if not constraint_exists('batch', LEGACY_BATCH_LABEL_CONSTRAINT):
            op.create_unique_constraint(LEGACY_BATCH_LABEL_CONSTRAINT, 'batch', ['label_code'])


def _drop_sqlite_unique(batch_op, constraint_name, columns):
    target = tuple(columns)
    removed = False

    named = getattr(batch_op.impl, 'named_constraints', {})
    if constraint_name and constraint_name in named:
        named.pop(constraint_name, None)
        removed = True

    if not removed:
        for name, constraint in list(named.items()):
            if isinstance(constraint, sa.UniqueConstraint):
                col_names = tuple(col.name for col in constraint.columns)
                if col_names == target:
                    named.pop(name, None)
                    removed = True
                    break

    if not removed:
        for constraint in list(getattr(batch_op.impl, 'unnamed_constraints', [])):
            if isinstance(constraint, sa.UniqueConstraint):
                col_names = tuple(col.name for col in constraint.columns)
                if col_names == target:
                    batch_op.impl.unnamed_constraints.remove(constraint)
                    removed = True
                    break

    return removed


def _dedupe_legacy_label_codes():
    """Normalize duplicate label_code values before recreating the legacy unique constraint."""
    if not table_exists('batch'):
        return
    bind = op.get_bind()
    duplicates = list(
        bind.execute(
            text(
                """
                WITH ranked AS (
                    SELECT
                        id,
                        label_code,
                        row_number() OVER (PARTITION BY label_code ORDER BY id) AS rn
                    FROM batch
                    WHERE label_code IS NOT NULL
                )
                SELECT id, label_code
                FROM ranked
                WHERE rn > 1
                """
            )
        )
    )
    for row in duplicates:
        new_code = f"{row.label_code}-{row.id}"
        bind.execute(
            text("UPDATE batch SET label_code = :code WHERE id = :id"),
            {"code": new_code[:255], "id": row.id},
        )


def _ensure_unit_indexes():
    if not index_exists('unit', 'ix_unit_active_scope_sort'):
        op.create_index('ix_unit_active_scope_sort', 'unit', ['is_active', 'is_custom', 'unit_type', 'name'])
    if not index_exists('unit', 'ix_unit_custom_org_scope'):
        op.create_index(
            'ix_unit_custom_org_scope',
            'unit',
            ['organization_id', 'is_active', 'is_custom', 'unit_type', 'name'],
        )


def _drop_unit_indexes():
    safe_drop_index('ix_unit_custom_org_scope', 'unit')
    safe_drop_index('ix_unit_active_scope_sort', 'unit')


def _ensure_hot_path_indexes():
    safe_create_index('ix_product_org_active', 'product', ['organization_id', 'is_active'])
    safe_create_index('ix_user_org_created_at', 'user', ['organization_id', 'created_at'])
    safe_create_index('ix_user_active_type', 'user', ['is_active', 'user_type'])
    safe_create_index('ix_user_organization_id', 'user', ['organization_id'])
    safe_create_index('ix_batch_org_status_started_at', 'batch', ['organization_id', 'status', 'started_at'])
    safe_create_index('ix_global_item_archive_type_name', 'global_item', ['is_archived', 'item_type', 'name'])


def _drop_hot_path_indexes():
    safe_drop_index('ix_global_item_archive_type_name', 'global_item')
    safe_drop_index('ix_batch_org_status_started_at', 'batch')
    safe_drop_index('ix_user_active_type', 'user')
    safe_drop_index('ix_user_org_created_at', 'user')
    safe_drop_index('ix_user_organization_id', 'user')
    safe_drop_index('ix_product_org_active', 'product')


def _drop_recipe_marketplace_columns():
    recipe_indexes = [
        'ix_recipe_org_origin_purchased',
        'ix_recipe_org_origin_source_org_id',
        'ix_recipe_org_origin_type',
        'ix_recipe_org_origin_recipe_id',
        'ix_recipe_purchase_count',
        'ix_recipe_download_count',
        'ix_recipe_origin_organization_id',
        'ix_recipe_origin_recipe_id',
        'ix_recipe_product_store_url',
        'ix_recipe_is_sellable',
        'ix_recipe_marketplace_status',
        'ix_recipe_is_for_sale',
        'ix_recipe_is_public',
        'ix_recipe_sharing_scope',
    ]
    for index_name in recipe_indexes:
        safe_drop_index(index_name, 'recipe')

    recipe_foreign_keys = [
        'fk_recipe_origin_org_id',
        'fk_recipe_origin_recipe_id',
        'fk_recipe_org_origin_source_org_id',
        'fk_recipe_org_origin_source_recipe_id',
        'fk_recipe_org_origin_recipe_id',
    ]
    for fk_name in recipe_foreign_keys:
        safe_drop_foreign_key(fk_name, 'recipe')

    recipe_columns = [
        'is_sellable',
        'origin_organization_id',
        'origin_recipe_id',
        'org_origin_purchased',
        'org_origin_source_recipe_id',
        'org_origin_source_org_id',
        'org_origin_type',
        'org_origin_recipe_id',
        'purchase_count',
        'download_count',
        'public_description',
        'skin_opt_in',
        'cover_image_url',
        'cover_image_path',
        'product_store_url',
        'shopify_product_url',
        'marketplace_violation_count',
        'marketplace_notes',
        'marketplace_status',
        'sale_price',
        'is_for_sale',
        'is_public',
        'sharing_scope',
        'status',
    ]
    for column_name in recipe_columns:
        safe_drop_column('recipe', column_name, verbose=False)