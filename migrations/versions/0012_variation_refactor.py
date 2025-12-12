"""Replace physical form linkage with variation table"""
from __future__ import annotations

import re
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import expression


# revision identifiers, used by Alembic.
revision = "0012_variation_refactor"
down_revision = "0011_ingredient_hierarchy_0011_ingredient_hierarchy"
branch_labels = None
depends_on = None


def _slugify(value: str | None) -> str | None:
    if not value:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or None


def upgrade():
    op.create_table(
        "variation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=128), nullable=True, unique=True),
        sa.Column("physical_form_id", sa.Integer(), sa.ForeignKey("physical_form.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_unit", sa.String(length=32), nullable=True),
        sa.Column("form_bypass", sa.Boolean(), nullable=False, server_default=expression.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=expression.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_variation_name", "variation", ["name"], unique=True)
    op.create_index("ix_variation_slug", "variation", ["slug"], unique=True)

    op.add_column("global_item", sa.Column("variation_id", sa.Integer(), nullable=True))
    op.create_index("ix_global_item_variation_id", "global_item", ["variation_id"])
    op.create_foreign_key(
        "fk_global_item_variation",
        "global_item",
        "variation",
        ["variation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=bind, only=("physical_form", "variation", "global_item"))
    physical_form_table = sa.Table("physical_form", meta, autoload_with=bind)
    variation_table = sa.Table("variation", meta, autoload_with=bind)
    global_item_table = sa.Table("global_item", meta, autoload_with=bind)

    now = datetime.utcnow()
    form_rows = list(
        bind.execute(
            sa.select(
                physical_form_table.c.id,
                physical_form_table.c.name,
                physical_form_table.c.slug,
                physical_form_table.c.description,
                physical_form_table.c.is_active,
            )
        )
    )
    form_to_variation: dict[int, int] = {}
    for row in form_rows:
        name = row.name or f"Physical Form {row.id}"
        slug = row.slug or _slugify(name) or f"variation-{row.id}"
        insert_stmt = variation_table.insert().values(
            name=name,
            slug=slug,
            physical_form_id=row.id,
            description=row.description,
            default_unit=None,
            form_bypass=False,
            is_active=row.is_active if row.is_active is not None else True,
            created_at=now,
            updated_at=now,
        )
        result = bind.execute(insert_stmt)
        form_to_variation[row.id] = result.inserted_primary_key[0]

    if form_to_variation:
        for form_id, variation_id in form_to_variation.items():
            update_stmt = (
                global_item_table.update()
                .where(global_item_table.c.physical_form_id == form_id)
                .values(variation_id=variation_id)
            )
            bind.execute(update_stmt)

    op.drop_constraint("fk_global_item_physical_form", "global_item", type_="foreignkey")
    op.drop_index("ix_global_item_physical_form_id", table_name="global_item")
    op.drop_column("global_item", "physical_form_id")


def downgrade():
    op.add_column("global_item", sa.Column("physical_form_id", sa.Integer(), nullable=True))
    op.create_index("ix_global_item_physical_form_id", "global_item", ["physical_form_id"])
    op.create_foreign_key(
        "fk_global_item_physical_form",
        "global_item",
        "physical_form",
        ["physical_form_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=bind, only=("variation", "global_item"))
    variation_table = sa.Table("variation", meta, autoload_with=bind)
    global_item_table = sa.Table("global_item", meta, autoload_with=bind)

    rows = list(
        bind.execute(
            sa.select(
                variation_table.c.id,
                variation_table.c.physical_form_id,
            )
        )
    )
    for row in rows:
        if not row.physical_form_id:
            continue
        update_stmt = (
            global_item_table.update()
            .where(global_item_table.c.variation_id == row.id)
            .values(physical_form_id=row.physical_form_id)
        )
        bind.execute(update_stmt)

    op.drop_constraint("fk_global_item_variation", "global_item", type_="foreignkey")
    op.drop_index("ix_global_item_variation_id", table_name="global_item")
    op.drop_column("global_item", "variation_id")

    op.drop_index("ix_variation_slug", table_name="variation")
    op.drop_index("ix_variation_name", table_name="variation")
    op.drop_table("variation")