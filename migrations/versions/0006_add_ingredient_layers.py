"""0006 add ingredient layers

Revision ID: 0006_add_ingredient_layers
Revises: 0005_cleanup_guardrails
Create Date: 2025-11-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.sql import func
from datetime import datetime
import re


# revision identifiers, used by Alembic.
revision = '0006_add_ingredient_layers'
down_revision = '0005_cleanup_guardrails'
branch_labels = None
depends_on = None


def _slugify(value: str) -> str:
    value = value or ''
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value or 'item'


def _unique_slug(session, model, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while session.query(model).filter_by(slug=slug).first():
        counter += 1
        slug = f"{base_slug}-{counter}"
    return slug


def upgrade():
    op.create_table(
        'ingredient',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False, unique=True),
        sa.Column('inci_name', sa.String(length=255), nullable=True),
        sa.Column('cas_number', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('is_active_ingredient', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'physical_form',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('slug', sa.String(length=128), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'function_tag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('slug', sa.String(length=128), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('function_tag.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'application_tag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('slug', sa.String(length=128), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('application_tag.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'global_item_function_tag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
        sa.Column('function_tag_id', sa.Integer(), sa.ForeignKey('function_tag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('global_item_id', 'function_tag_id', name='uq_global_item_function_tag'),
    )

    op.create_table(
        'global_item_application_tag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('global_item_id', sa.Integer(), sa.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False),
        sa.Column('application_tag_id', sa.Integer(), sa.ForeignKey('application_tag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('global_item_id', 'application_tag_id', name='uq_global_item_application_tag'),
    )

    op.create_index('ix_global_item_function_tag_item', 'global_item_function_tag', ['global_item_id'])
    op.create_index('ix_global_item_function_tag_tag', 'global_item_function_tag', ['function_tag_id'])
    op.create_index('ix_global_item_application_tag_item', 'global_item_application_tag', ['global_item_id'])
    op.create_index('ix_global_item_application_tag_tag', 'global_item_application_tag', ['application_tag_id'])

    op.add_column('global_item', sa.Column('ingredient_id', sa.Integer(), nullable=True))
    op.add_column('global_item', sa.Column('physical_form_id', sa.Integer(), nullable=True))

    op.create_foreign_key('fk_global_item_ingredient', 'global_item', 'ingredient', ['ingredient_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_global_item_physical_form', 'global_item', 'physical_form', ['physical_form_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_global_item_ingredient_id', 'global_item', ['ingredient_id'])
    op.create_index('ix_global_item_physical_form_id', 'global_item', ['physical_form_id'])

    bind = op.get_bind()
    session = orm.Session(bind=bind)

    Base = orm.declarative_base()

    class IngredientProfile(Base):
        __tablename__ = 'ingredient'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String)
        slug = sa.Column(sa.String)
        inci_name = sa.Column(sa.String)
        cas_number = sa.Column(sa.String)
        description = sa.Column(sa.Text)
        aliases = sa.Column(sa.JSON)
        is_active_ingredient = sa.Column(sa.Boolean)
        created_at = sa.Column(sa.DateTime)
        updated_at = sa.Column(sa.DateTime)

    class PhysicalForm(Base):
        __tablename__ = 'physical_form'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String)
        slug = sa.Column(sa.String)
        description = sa.Column(sa.Text)
        is_active = sa.Column(sa.Boolean)
        created_at = sa.Column(sa.DateTime)
        updated_at = sa.Column(sa.DateTime)

    class GlobalItem(Base):
        __tablename__ = 'global_item'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String)
        item_type = sa.Column(sa.String)
        ingredient_id = sa.Column(sa.Integer)
        physical_form_id = sa.Column(sa.Integer)
        metadata_json = sa.Column(sa.JSON)

    try:
        # Seed baseline physical forms
        default_forms = [
            ('unspecified', 'Unspecified'),
            ('whole', 'Whole'),
            ('cut-sifted', 'Cut & Sifted'),
            ('powder', 'Powder'),
            ('liquid', 'Liquid'),
            ('paste', 'Paste'),
            ('granule', 'Granule'),
            ('flake', 'Flake'),
        ]
        existing_forms = {
            pf.slug: pf.id for pf in session.query(PhysicalForm).all()
        }
        for slug, name in default_forms:
            if slug in existing_forms:
                continue
            pf = PhysicalForm(
                name=name,
                slug=slug,
                description=None,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(pf)
        session.flush()

        def ensure_physical_form(name: str):
            base_name = (name or '').strip()
            if not base_name:
                base_name = 'Unspecified'
            slug = _slugify(base_name)
            pf = session.query(PhysicalForm).filter_by(slug=slug).first()
            if pf:
                return pf
            unique_slug = _unique_slug(session, PhysicalForm, slug)
            pf = PhysicalForm(
                name=base_name,
                slug=unique_slug,
                description=None,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(pf)
            session.flush()
            return pf

        def ensure_ingredient(item: GlobalItem):
            source_name = (item.name or '').strip() or 'Unnamed Item'
            base_name = source_name
            # Attempt to strip parenthetical physical form descriptors
            if '(' in base_name and base_name.endswith(')'):
                candidate = base_name.split('(')[0].strip()
                if candidate:
                    base_name = candidate

            slug = _slugify(base_name)
            ingredient = session.query(IngredientProfile).filter_by(slug=slug).first()
            if ingredient:
                return ingredient
            unique_slug = _unique_slug(session, IngredientProfile, slug)
            ingredient = IngredientProfile(
                name=base_name,
                slug=unique_slug,
                inci_name=None,
                cas_number=None,
                description=None,
                aliases=None,
                is_active_ingredient=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(ingredient)
            session.flush()
            return ingredient

        physical_form_lookup = {pf.slug: pf for pf in session.query(PhysicalForm).all()}

        for item in session.query(GlobalItem).all():
            ingredient = ensure_ingredient(item)
            # Naive physical form inference
            name_lower = (item.name or '').lower()
            if 'powder' in name_lower:
                pf = ensure_physical_form('Powder')
            elif 'cut' in name_lower or 'sift' in name_lower:
                pf = ensure_physical_form('Cut & Sifted')
            elif 'whole' in name_lower or 'leaf' in name_lower:
                pf = ensure_physical_form('Whole')
            elif 'liquid' in name_lower or 'hydrosol' in name_lower or 'water' in name_lower:
                pf = ensure_physical_form('Liquid')
            elif 'granule' in name_lower:
                pf = ensure_physical_form('Granule')
            elif 'flake' in name_lower:
                pf = ensure_physical_form('Flake')
            elif 'paste' in name_lower:
                pf = ensure_physical_form('Paste')
            else:
                pf = ensure_physical_form('Unspecified')

            item.ingredient_id = ingredient.id
            item.physical_form_id = pf.id

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    op.alter_column('global_item', 'ingredient_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('global_item', 'physical_form_id', existing_type=sa.Integer(), nullable=False)


def downgrade():
    op.drop_index('ix_global_item_physical_form_id', table_name='global_item')
    op.drop_index('ix_global_item_ingredient_id', table_name='global_item')
    op.drop_constraint('fk_global_item_physical_form', 'global_item', type_='foreignkey')
    op.drop_constraint('fk_global_item_ingredient', 'global_item', type_='foreignkey')
    op.drop_column('global_item', 'physical_form_id')
    op.drop_column('global_item', 'ingredient_id')

    op.drop_index('ix_global_item_application_tag_tag', table_name='global_item_application_tag')
    op.drop_index('ix_global_item_application_tag_item', table_name='global_item_application_tag')
    op.drop_table('global_item_application_tag')
    op.drop_index('ix_global_item_function_tag_tag', table_name='global_item_function_tag')
    op.drop_index('ix_global_item_function_tag_item', table_name='global_item_function_tag')
    op.drop_table('global_item_function_tag')
    op.drop_table('application_tag')
    op.drop_table('function_tag')
    op.drop_table('physical_form')
    op.drop_table('ingredient')

