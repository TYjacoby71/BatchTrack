"""0013 recipe origin and org marketplace

Revision ID: 0013_recipe_family
Revises: 0012_recipe_public_description
Create Date: 2025-11-24 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    safe_add_column,
    safe_drop_column,
    safe_create_index,
    safe_drop_index,
    safe_create_foreign_key,
    safe_drop_foreign_key,
)

# revision identifiers, used by Alembic.
revision = "0013_recipe_family"
down_revision = "0012_recipe_public_description"
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        "recipe",
        sa.Column("org_origin_recipe_id", sa.Integer(), nullable=True),
    )
    safe_add_column(
        "recipe",
        sa.Column(
            "org_origin_type",
            sa.String(length=32),
            nullable=False,
            server_default="authored",
        ),
    )
    safe_add_column(
        "recipe",
        sa.Column("org_origin_source_org_id", sa.Integer(), nullable=True),
    )
    safe_add_column(
        "recipe",
        sa.Column("org_origin_source_recipe_id", sa.Integer(), nullable=True),
    )
    safe_add_column(
        "recipe",
        sa.Column(
            "org_origin_purchased",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    safe_add_column(
        "recipe",
        sa.Column(
            "download_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    safe_add_column(
        "recipe",
        sa.Column(
            "purchase_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    safe_add_column(
        "recipe",
        sa.Column("product_store_url", sa.String(length=500), nullable=True),
    )

    safe_create_index(
        "ix_recipe_org_origin_recipe_id",
        "recipe",
        ["org_origin_recipe_id"],
    )
    safe_create_index(
        "ix_recipe_org_origin_type",
        "recipe",
        ["org_origin_type"],
    )
    safe_create_index(
        "ix_recipe_org_origin_source_org_id",
        "recipe",
        ["org_origin_source_org_id"],
    )
    safe_create_index(
        "ix_recipe_org_origin_purchased",
        "recipe",
        ["org_origin_purchased"],
    )
    safe_create_index(
        "ix_recipe_download_count",
        "recipe",
        ["download_count"],
    )
    safe_create_index(
        "ix_recipe_purchase_count",
        "recipe",
        ["purchase_count"],
    )
    safe_create_index(
        "ix_recipe_product_store_url",
        "recipe",
        ["product_store_url"],
    )

    safe_create_foreign_key(
        "fk_recipe_org_origin_recipe_id",
        "recipe",
        "recipe",
        ["org_origin_recipe_id"],
        ["id"],
    )
    safe_create_foreign_key(
        "fk_recipe_org_origin_source_recipe_id",
        "recipe",
        "recipe",
        ["org_origin_source_recipe_id"],
        ["id"],
    )
    safe_create_foreign_key(
        "fk_recipe_org_origin_source_org_id",
        "recipe",
        "organization",
        ["org_origin_source_org_id"],
        ["id"],
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE recipe
            SET org_origin_recipe_id = COALESCE(root_recipe_id, id)
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE recipe
            SET org_origin_type = CASE
                WHEN organization_id = :batchtrack_org_id THEN 'batchtrack_native'
                ELSE 'authored'
            END
            WHERE org_origin_type IS NULL OR org_origin_type = ''
            """
        ),
        {"batchtrack_org_id": 1},
    )


def downgrade():
    safe_drop_foreign_key(
        "fk_recipe_org_origin_source_org_id",
        "recipe",
    )
    safe_drop_foreign_key(
        "fk_recipe_org_origin_source_recipe_id",
        "recipe",
    )
    safe_drop_foreign_key(
        "fk_recipe_org_origin_recipe_id",
        "recipe",
    )

    safe_drop_index("ix_recipe_purchase_count", "recipe")
    safe_drop_index("ix_recipe_download_count", "recipe")
    safe_drop_index("ix_recipe_org_origin_purchased", "recipe")
    safe_drop_index("ix_recipe_org_origin_source_org_id", "recipe")
    safe_drop_index("ix_recipe_org_origin_type", "recipe")
    safe_drop_index("ix_recipe_org_origin_recipe_id", "recipe")

    safe_drop_index("ix_recipe_product_store_url", "recipe")

    safe_drop_column("recipe", "product_store_url")
    safe_drop_column("recipe", "purchase_count")
    safe_drop_column("recipe", "download_count")
    safe_drop_column("recipe", "org_origin_purchased")
    safe_drop_column("recipe", "org_origin_source_recipe_id")
    safe_drop_column("recipe", "org_origin_source_org_id")
    safe_drop_column("recipe", "org_origin_type")
    safe_drop_column("recipe", "org_origin_recipe_id")
