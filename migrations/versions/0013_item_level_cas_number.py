"""Add cas_number to global_item (item-level CAS).

This supports storing CAS at the global item level,
since CAS can differ across variations/forms (e.g., extract vs oil vs whole herb).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0013_item_level_cas_number"
down_revision = "0012_variation_refactor"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("global_item", sa.Column("cas_number", sa.String(length=64), nullable=True))

    # Best-effort backfill:
    # - Copy IngredientDefinition.cas_number -> GlobalItem.cas_number when missing.
    bind = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=bind, only=("global_item", "ingredient"))

    global_item = sa.Table("global_item", meta, autoload_with=bind)
    ingredient = sa.Table("ingredient", meta, autoload_with=bind)

    try:
        gi_rows = list(
            bind.execute(
                sa.select(global_item.c.id, ingredient.c.cas_number)
                .select_from(global_item.join(ingredient, global_item.c.ingredient_id == ingredient.c.id))
                .where(
                    global_item.c.cas_number.is_(None),
                    ingredient.c.cas_number.is_not(None),
                )
            )
        )
        for row in gi_rows:
            bind.execute(
                global_item.update()
                .where(global_item.c.id == row.id)
                .values(cas_number=row.cas_number)
            )
    except Exception:
        # Defensive: do not fail migration on backfill issues.
        pass

def downgrade():
    op.drop_column("global_item", "cas_number")

