"""0006 recipe lineage upgrade

Revision ID: 0006_recipe_lineage_upgrade
Revises: 0005_cleanup_guardrails
Create Date: 2025-11-14 18:32:00.000000
"""

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

    _backfill_root_ids(bind)


def downgrade():
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
