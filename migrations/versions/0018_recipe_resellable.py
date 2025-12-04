"""add is_resellable flag to recipes

Revision ID: 0018_recipe_resellable
Revises: 0017_hot_query_indexes
Create Date: 2025-12-04 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0018_recipe_resellable"
down_revision = "0017_hot_query_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recipe",
        sa.Column(
            "is_resellable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        "UPDATE recipe SET is_resellable = false WHERE org_origin_purchased = true"
    )


def downgrade():
    op.drop_column("recipe", "is_resellable")
