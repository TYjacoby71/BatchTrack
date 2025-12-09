"""0011 ingredient hierarchy and tagging layer

Revision ID: 0011_ingredient_hierarchy
Revises: 0010_recipe_status_drafts
Create Date: 2025-11-12 18:22:00.000000

"""
from datetime import datetime
import re

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    safe_add_column,
    safe_drop_column,
    safe_create_index,
    safe_drop_index,
    safe_create_foreign_key,
    safe_drop_foreign_key,
    table_exists,
    column_exists,
)


# revision identifiers, used by Alembic.
revision = '0011_ingredient_hierarchy'
down_revision = '0010_recipe_status_drafts'
branch_labels = None
depends_on = None


_FORM_KEYWORDS = (
    'powder',
    'whole',
    'cut',
    'sifted',
    'granules',
    'granule',
    'flakes',
    'flake',
    'shredded',
    'shred',
    'ground',
    'liquid',
    'solid',
    'pellet',
    'pellets',
    'form',
    'extract',
    'concentrate',
    'paste',
    'powdered',
    'crushed',
)


def _slugify(value: str | None) -> str | None:
    if not value:
        return None
    slug = re.sub(r'[^a-z0-9]+', '-', value.strip().lower())
    slug = slug.strip('-')
    return slug or None


def _normalize_ingredient_name(value: str | None) -> str:
    if not value:
        return ''
    cleaned = value
    # Remove parenthetical form hints
    cleaned = re.sub(r'\s*\(.*?\)\s*', ' ', cleaned)
    # Replace separators with spaces
    cleaned = re.sub(r'[-_/]+', ' ', cleaned)
    parts = [part.strip() for part in cleaned.split(',') if part.strip()]
    if parts:
        cleaned = parts[0]
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    tokens = cleaned.split(' ')
    trimmed = []
    for token in tokens:
        lowered = token.lower()
        if lowered in _FORM_KEYWORDS:
            continue
        trimmed.append(token)
    normalized = ' '.join(trimmed).strip()
    return normalized or value.strip()


def upgrade():
    # Create core lookup tables
    if not table_exists('ingredient'):
        op.create_table(
            'ingredient',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('slug', sa.String(length=128), nullable=True, unique=True),
            sa.Column('ingredient_category_id', sa.Integer(), sa.ForeignKey('ingredient_category.id', ondelete='SET NULL'), nullable=True),
            sa.Column('inci_name', sa.String(length=256), nullable=True),
            sa.Column('cas_number', sa.String(length=64), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    safe_create_index('ix_ingredient_name', 'ingredient', ['name'])
    safe_create_index('ix_ingredient_slug', 'ingredient', ['slug'])
    safe_create_index('ix_ingredient_category_id', 'ingredient', ['ingredient_category_id'])

    if not table_exists('physical_form'):
        op.create_table(
            'physical_form',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=64), nullable=False, unique=True),
            sa.Column('slug', sa.String(length=64), nullable=True, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not table_exists('function_tag'):
        op.create_table(
            'function_tag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=64), nullable=False, unique=True),
            sa.Column('slug', sa.String(length=64), nullable=True, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not table_exists('application_tag'):
        op.create_table(
            'application_tag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=128), nullable=False, unique=True),
            sa.Column('slug', sa.String(length=128), nullable=True, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not table_exists('global_item_function_tag'):
        op.create_table(
            'global_item_function_tag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
            sa.Column('function_tag_id', sa.Integer(), sa.ForeignKey('function_tag.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('global_item_id', 'function_tag_id', name='uq_global_item_function_tag'),
        )
    safe_create_index('ix_global_item_function_tag_item', 'global_item_function_tag', ['global_item_id'])
    safe_create_index('ix_global_item_function_tag_function', 'global_item_function_tag', ['function_tag_id'])

    if not table_exists('global_item_application_tag'):
        op.create_table(
            'global_item_application_tag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
            sa.Column('application_tag_id', sa.Integer(), sa.ForeignKey('application_tag.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('global_item_id', 'application_tag_id', name='uq_global_item_application_tag'),
        )
    safe_create_index('ix_global_item_application_tag_item', 'global_item_application_tag', ['global_item_id'])
    safe_create_index('ix_global_item_application_tag_application', 'global_item_application_tag', ['application_tag_id'])

    if not table_exists('ingredient_category_tag'):
        op.create_table(
            'ingredient_category_tag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=128), nullable=False, unique=True),
            sa.Column('slug', sa.String(length=128), nullable=True, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    safe_create_index('ix_ingredient_category_tag_slug', 'ingredient_category_tag', ['slug'])

    if not table_exists('global_item_category_tag'):
        op.create_table(
            'global_item_category_tag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
            sa.Column('ingredient_category_tag_id', sa.Integer(), sa.ForeignKey('ingredient_category_tag.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('global_item_id', 'ingredient_category_tag_id', name='uq_global_item_category_tag'),
        )
    safe_create_index('ix_global_item_category_tag_item', 'global_item_category_tag', ['global_item_id'])
    safe_create_index('ix_global_item_category_tag_category', 'global_item_category_tag', ['ingredient_category_tag_id'])

    # Extend global_item with ingredient + physical form references
    safe_add_column('global_item', sa.Column('ingredient_id', sa.Integer(), nullable=True))
    safe_add_column('global_item', sa.Column('physical_form_id', sa.Integer(), nullable=True))
    safe_create_index('ix_global_item_ingredient_id', 'global_item', ['ingredient_id'])
    safe_create_index('ix_global_item_physical_form_id', 'global_item', ['physical_form_id'])
    safe_create_foreign_key(
        'fk_global_item_ingredient',
        'global_item',
        'ingredient',
        ['ingredient_id'],
        ['id'],
        ondelete='SET NULL',
    )
    safe_create_foreign_key(
        'fk_global_item_physical_form',
        'global_item',
        'physical_form',
        ['physical_form_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Backfill canonical ingredient rows for existing ingredient-type items
    bind = op.get_bind()
    meta = sa.MetaData()
    meta.bind = bind
    global_item_table = sa.Table('global_item', meta, autoload_with=bind)
    ingredient_table = sa.Table('ingredient', meta, autoload_with=bind)
    ingredient_category_table = sa.Table('ingredient_category', meta, autoload_with=bind)
    ingredient_category_tag_table = sa.Table('ingredient_category_tag', meta, autoload_with=bind)
    global_item_category_tag_table = sa.Table('global_item_category_tag', meta, autoload_with=bind)

    now = datetime.utcnow()
    select_stmt = sa.select(
        global_item_table.c.id,
        global_item_table.c.name,
        global_item_table.c.inci_name,
        global_item_table.c.ingredient_category_id,
    ).where(global_item_table.c.item_type == 'ingredient').order_by(global_item_table.c.id)

    rows = list(bind.execute(select_stmt))

    ingredient_groups: dict[str, dict] = {}
    for row in rows:
        normalized = _normalize_ingredient_name(row.name)
        if not normalized:
            normalized = row.name
        group = ingredient_groups.setdefault(
            normalized,
            {
                'sample': row,
                'ids': [],
            },
        )
        group['ids'].append(row.id)

    name_to_ingredient_id: dict[str, int] = {}
    for normalized_name, payload in ingredient_groups.items():
        sample = payload['sample']
        slug_value = _slugify(normalized_name) or f"ingredient-{sample.id}"
        insert_stmt = ingredient_table.insert().values(
            name=normalized_name,
            slug=slug_value,
            inci_name=sample.inci_name,
            ingredient_category_id=sample.ingredient_category_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        result = bind.execute(insert_stmt)
        name_to_ingredient_id[normalized_name] = result.inserted_primary_key[0]

    for normalized_name, payload in ingredient_groups.items():
        ingredient_id = name_to_ingredient_id.get(normalized_name)
        if not ingredient_id:
            continue
        id_chunk = payload['ids']
        if not id_chunk:
            continue
        update_stmt = (
            global_item_table.update()
            .where(global_item_table.c.id.in_(id_chunk))
            .values(ingredient_id=ingredient_id)
        )
        bind.execute(update_stmt)

    # Seed ingredient_category_tag entries mirroring existing categories
    category_rows = list(
        bind.execute(
            sa.select(
                ingredient_category_table.c.id,
                ingredient_category_table.c.name,
                ingredient_category_table.c.description,
            )
        )
    )
    category_tag_map = {}
    for category in category_rows:
        if not category.name:
            continue
        slug = _slugify(category.name) or f"ingredient-category-{category.id}"
        insert_stmt = ingredient_category_tag_table.insert().values(
            name=category.name,
            slug=slug,
            description=category.description,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        result = bind.execute(insert_stmt)
        category_tag_map[category.id] = result.inserted_primary_key[0]

    # Link existing global items to their converted category tags
    for row in rows:
        category_id = row.ingredient_category_id
        tag_id = category_tag_map.get(category_id)
        if not tag_id:
            continue
        bind.execute(
            global_item_category_tag_table.insert().values(
                global_item_id=row.id,
                ingredient_category_tag_id=tag_id,
                created_at=now,
            )
        )


def downgrade():
    # Drop relationships and columns from global_item first
    op.drop_constraint('fk_global_item_physical_form', 'global_item', type_='foreignkey')
    op.drop_constraint('fk_global_item_ingredient', 'global_item', type_='foreignkey')
    op.drop_index('ix_global_item_physical_form_id', table_name='global_item')
    op.drop_index('ix_global_item_ingredient_id', table_name='global_item')

    with op.batch_alter_table('global_item') as batch_op:
        batch_op.drop_column('physical_form_id')
        batch_op.drop_column('ingredient_id')

    # Drop association tables and lookup tables
    safe_drop_index('ix_global_item_category_tag_category', 'global_item_category_tag')
    safe_drop_index('ix_global_item_category_tag_item', 'global_item_category_tag')
    op.drop_table('global_item_category_tag')

    safe_drop_index('ix_ingredient_category_tag_slug', 'ingredient_category_tag')
    op.drop_table('ingredient_category_tag')

    safe_drop_index('ix_global_item_application_tag_application', 'global_item_application_tag')
    safe_drop_index('ix_global_item_application_tag_item', 'global_item_application_tag')
    op.drop_table('global_item_application_tag')

    safe_drop_index('ix_global_item_function_tag_function', 'global_item_function_tag')
    safe_drop_index('ix_global_item_function_tag_item', 'global_item_function_tag')
    op.drop_table('global_item_function_tag')

    op.drop_table('application_tag')
    op.drop_table('function_tag')
    op.drop_table('physical_form')
    safe_drop_index('ix_ingredient_category_id', 'ingredient')
    safe_drop_index('ix_ingredient_slug', 'ingredient')
    safe_drop_index('ix_ingredient_name', 'ingredient')
    op.drop_table('ingredient')
