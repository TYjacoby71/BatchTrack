"""0006 recipe lineage upgrade

Revision ID: 0006_recipe_lineage_upgrade
Revises: 0005_cleanup_guardrails
Create Date: 2025-11-14 18:32:00.000000
"""

import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from migrations.postgres_helpers import (
    safe_add_column,
    safe_drop_column,
    safe_create_index,
    safe_drop_index,
    safe_create_foreign_key,
    safe_drop_foreign_key,
    safe_batch_alter_table,
    table_exists,
    column_exists,
)


# revision identifiers, used by Alembic.
revision = '0006_recipe_lineage_upgrade'
down_revision = '0005_cleanup_guardrails'
branch_labels = None
depends_on = None


def _rename_parent_column():
    """Rename recipe.parent_id -> parent_recipe_id if needed."""
    if not table_exists('recipe'):
        return
    if not column_exists('recipe', 'parent_id'):
        return
    if column_exists('recipe', 'parent_recipe_id'):
        return

    with safe_batch_alter_table('recipe') as batch_op:
        batch_op.alter_column('parent_id', new_column_name='parent_recipe_id', existing_type=sa.Integer)


def _ensure_backup_table():
    """Create the lineage backup table if it does not already exist."""
    if table_exists('recipe_lineage_backup'):
        return
    op.create_table(
        'recipe_lineage_backup',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('snapshot', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def _store_lineage_backup(bind):
    """Persist lineage metadata so downgrades can restore on re-upgrade."""
    if not table_exists('recipe'):
        return

    metadata = sa.MetaData()
    reflect_tables = ['recipe']
    if table_exists('recipe_lineage'):
        reflect_tables.append('recipe_lineage')
    metadata.reflect(bind=bind, only=reflect_tables)

    recipe_table = metadata.tables['recipe']
    lineage_table = metadata.tables.get('recipe_lineage')

    recipe_rows = bind.execute(
        sa.select(
            recipe_table.c.id,
            recipe_table.c.parent_recipe_id,
            recipe_table.c.cloned_from_id,
            recipe_table.c.root_recipe_id
        )
    ).mappings().all()

    lineage_rows = []
    if lineage_table is not None:
        lineage_rows = bind.execute(
            sa.select(
                lineage_table.c.recipe_id,
                lineage_table.c.source_recipe_id,
                lineage_table.c.event_type,
                lineage_table.c.user_id,
                lineage_table.c.notes,
                lineage_table.c.organization_id,
                lineage_table.c.created_at
            )
        ).mappings().all()

    payload = {
        'recipes': [dict(row) for row in recipe_rows if any(row[k] is not None for k in ('parent_recipe_id', 'cloned_from_id', 'root_recipe_id'))],
        'lineage': [dict(row) for row in lineage_rows],
    }

    if not payload['recipes'] and not payload['lineage']:
        return

    _ensure_backup_table()
    metadata.reflect(bind=bind, only=['recipe_lineage_backup'])
    backup_table = metadata.tables['recipe_lineage_backup']
    bind.execute(
        backup_table.insert().values(
            snapshot=json.dumps(payload, default=str)
        )
    )


def _restore_lineage_from_backup(bind):
    """Rehydrate lineage metadata captured during downgrade."""
    if not table_exists('recipe_lineage_backup'):
        return

    metadata = sa.MetaData()
    metadata.reflect(bind=bind, only=['recipe_lineage_backup'])
    backup_table = metadata.tables['recipe_lineage_backup']

    latest = bind.execute(
        sa.select(
            backup_table.c.id,
            backup_table.c.snapshot
        ).order_by(backup_table.c.id.desc())
    ).first()

    if not latest:
        op.drop_table('recipe_lineage_backup')
        return

    snapshot = latest.snapshot
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except json.JSONDecodeError:
            snapshot = None

    if not snapshot:
        bind.execute(backup_table.delete().where(backup_table.c.id == latest.id))
        op.drop_table('recipe_lineage_backup')
        return

    target_tables = ['recipe']
    if table_exists('recipe_lineage'):
        target_tables.append('recipe_lineage')
    target_metadata = sa.MetaData()
    target_metadata.reflect(bind=bind, only=target_tables)
    recipe_table = target_metadata.tables['recipe']
    lineage_table = target_metadata.tables.get('recipe_lineage')

    for row in snapshot.get('recipes', []):
        stmt = (
            recipe_table.update()
            .where(recipe_table.c.id == row.get('id'))
            .values(
                parent_recipe_id=row.get('parent_recipe_id'),
                cloned_from_id=row.get('cloned_from_id'),
                root_recipe_id=row.get('root_recipe_id')
            )
        )
        bind.execute(stmt)

    lineage_payload = snapshot.get('lineage') or []
    if lineage_payload and lineage_table is not None:
        # Sanitize lineage rows to avoid FK violations on restore.
        recipe_ids = set(
            bind.execute(sa.select(recipe_table.c.id)).scalars().all()
        )

        organization_ids: set[int] = set()
        if table_exists('organization'):
            org_metadata = sa.MetaData()
            org_metadata.reflect(bind=bind, only=['organization'])
            org_table = org_metadata.tables['organization']
            organization_ids = set(
                bind.execute(sa.select(org_table.c.id)).scalars().all()
            )

        user_ids: set[int] = set()
        if table_exists('user'):
            user_metadata = sa.MetaData()
            user_metadata.reflect(bind=bind, only=['user'])
            user_table = user_metadata.tables['user']
            user_ids = set(
                bind.execute(sa.select(user_table.c.id)).scalars().all()
            )

        sanitized_payload = []
        for item in lineage_payload:
            recipe_id = item.get('recipe_id')
            if recipe_id is None or recipe_id not in recipe_ids:
                continue

            source_recipe_id = item.get('source_recipe_id')
            if source_recipe_id is not None and source_recipe_id not in recipe_ids:
                source_recipe_id = None

            organization_id = item.get('organization_id')
            if organization_id is not None and organization_id not in organization_ids:
                organization_id = None

            user_id = item.get('user_id')
            if user_id is not None and user_id not in user_ids:
                user_id = None

            sanitized_payload.append(
                {
                    'recipe_id': recipe_id,
                    'source_recipe_id': source_recipe_id,
                    'event_type': item.get('event_type'),
                    'user_id': user_id,
                    'notes': item.get('notes'),
                    'organization_id': organization_id,
                    'created_at': item.get('created_at'),
                }
            )

        if sanitized_payload:
            bind.execute(
                lineage_table.insert(),
                sanitized_payload
            )

    # Remove the consumed backup row and table to keep schema tidy when on 0006+
    bind.execute(backup_table.delete().where(backup_table.c.id == latest.id))
    op.drop_table('recipe_lineage_backup')


def _backfill_root_ids(bind):
    if not table_exists('recipe'):
        return

    metadata = sa.MetaData()
    metadata.reflect(bind=bind, only=['recipe'])
    recipe_table = metadata.tables['recipe']

    session = Session(bind=bind)
    try:
        rows = session.execute(
            sa.select(recipe_table.c.id, recipe_table.c.parent_recipe_id, recipe_table.c.root_recipe_id)
        ).all()
        parent_map = {row.id: row.parent_recipe_id for row in rows}
        cache: dict[int, int] = {}

        def resolve_root(recipe_id: int) -> int:
            if recipe_id in cache:
                return cache[recipe_id]
            seen = set()
            current = recipe_id
            parent = parent_map.get(current)
            while parent:
                if parent in seen:
                    break
                seen.add(parent)
                current = parent
                parent = parent_map.get(current)
            cache[recipe_id] = current
            return current

        for row in rows:
            if row.root_recipe_id:
                continue
            root_id = resolve_root(row.id)
            session.execute(
                sa.update(recipe_table)
                .where(recipe_table.c.id == row.id)
                .values(root_recipe_id=root_id or row.id)
            )
        session.commit()
    finally:
        session.close()


def upgrade():
    bind = op.get_bind()

    _rename_parent_column()

    # Add lineage columns
    safe_add_column('recipe', sa.Column('cloned_from_id', sa.Integer, nullable=True))
    safe_add_column('recipe', sa.Column('root_recipe_id', sa.Integer, nullable=True))

    # Create indexes for lineage columns
    safe_create_index('ix_recipe_parent_recipe_id', 'recipe', ['parent_recipe_id'])
    safe_create_index('ix_recipe_cloned_from_id', 'recipe', ['cloned_from_id'])
    safe_create_index('ix_recipe_root_recipe_id', 'recipe', ['root_recipe_id'])

    # Add FK constraints where supported
    safe_create_foreign_key('fk_recipe_parent_recipe_id', 'recipe', 'recipe', ['parent_recipe_id'], ['id'])
    safe_create_foreign_key('fk_recipe_cloned_from_id', 'recipe', 'recipe', ['cloned_from_id'], ['id'])
    safe_create_foreign_key('fk_recipe_root_recipe_id', 'recipe', 'recipe', ['root_recipe_id'], ['id'])

    # Create recipe_lineage table
    op.create_table(
        'recipe_lineage',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('organization_id', sa.Integer, sa.ForeignKey('organization.id'), nullable=True),
        sa.Column('recipe_id', sa.Integer, sa.ForeignKey('recipe.id'), nullable=False),
        sa.Column('source_recipe_id', sa.Integer, sa.ForeignKey('recipe.id'), nullable=True),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    safe_create_index('ix_recipe_lineage_recipe_id', 'recipe_lineage', ['recipe_id'])
    safe_create_index('ix_recipe_lineage_source_recipe_id', 'recipe_lineage', ['source_recipe_id'])
    safe_create_index('ix_recipe_lineage_event_type', 'recipe_lineage', ['event_type'])

    _restore_lineage_from_backup(bind)
    _backfill_root_ids(bind)


def downgrade():
    bind = op.get_bind()

    # Clean up any unified_inventory_history references before dropping tables/columns
    from migrations.postgres_helpers import is_postgresql
    if is_postgresql():
        # Check if batch_id column exists in unified_inventory_history
        unified_history_columns = bind.execute(sa.text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'unified_inventory_history' AND column_name = 'batch_id'
        """)).fetchone()
        if unified_history_columns:
            bind.execute(sa.text("""
                UPDATE unified_inventory_history SET batch_id = NULL WHERE batch_id IS NOT NULL
            """))

        # Check if used_for_batch_id column exists in unified_inventory_history
        used_for_batch_columns = bind.execute(sa.text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'unified_inventory_history' AND column_name = 'used_for_batch_id'
        """)).fetchone()
        if used_for_batch_columns:
            bind.execute(sa.text("""
                UPDATE unified_inventory_history SET used_for_batch_id = NULL WHERE used_for_batch_id IS NOT NULL
            """))
    else:
        # SQLite version
        # Check if batch_id column exists in unified_inventory_history
        unified_history_check = bind.execute(sa.text("""
            SELECT name FROM pragma_table_info('unified_inventory_history') WHERE name = 'batch_id'
        """)).fetchone()
        if unified_history_check:
            bind.execute(sa.text("""
                UPDATE unified_inventory_history SET batch_id = NULL WHERE batch_id IS NOT NULL
            """))

        # Check if used_for_batch_id column exists in unified_inventory_history  
        used_for_batch_check = bind.execute(sa.text("""
            SELECT name FROM pragma_table_info('unified_inventory_history') WHERE name = 'used_for_batch_id'
        """)).fetchone()
        if used_for_batch_check:
            bind.execute(sa.text("""
                UPDATE unified_inventory_history SET used_for_batch_id = NULL WHERE used_for_batch_id IS NOT NULL
            """))

    _store_lineage_backup(bind)

    # Drop lineage table
    if table_exists('recipe_lineage'):
        safe_drop_index('ix_recipe_lineage_event_type', 'recipe_lineage')
        safe_drop_index('ix_recipe_lineage_source_recipe_id', 'recipe_lineage')
        safe_drop_index('ix_recipe_lineage_recipe_id', 'recipe_lineage')
        op.drop_table('recipe_lineage')

    # Drop FK constraints if present
    safe_drop_foreign_key('fk_recipe_root_recipe_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_cloned_from_id', 'recipe')
    safe_drop_foreign_key('fk_recipe_parent_recipe_id', 'recipe')

    # Drop indexes
    safe_drop_index('ix_recipe_root_recipe_id', 'recipe')
    safe_drop_index('ix_recipe_cloned_from_id', 'recipe')
    safe_drop_index('ix_recipe_parent_recipe_id', 'recipe')

    # Drop columns
    safe_drop_column('recipe', 'root_recipe_id')
    safe_drop_column('recipe', 'cloned_from_id')

    # Rename column back if needed
    if column_exists('recipe', 'parent_recipe_id') and not column_exists('recipe', 'parent_id'):
        with safe_batch_alter_table('recipe') as batch_op:
            batch_op.alter_column('parent_recipe_id', new_column_name='parent_id', existing_type=sa.Integer)
