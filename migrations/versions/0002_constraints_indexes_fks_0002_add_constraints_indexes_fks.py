"""0002 add constraints/indexes/fks

Revision ID: 0002_constraints_indexes_fks
Revises: 0001_base_schema
Create Date: 2025-10-21 20:27:26.513838

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_constraints_indexes_fks'
down_revision = '0001_base_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Add foreign keys that may be complex or require explicit naming/order
    # Use explicit constraint names for clarity and idempotence
    # Example pattern:
    # op.create_foreign_key(
    #     "fk_child_parent",
    #     "child", "parent",
    #     local_cols=["parent_id"], remote_cols=["id"],
    #     ondelete="CASCADE"
    # )

    # Role-Permission many-to-many already created via association table in 0001
    # Create additional indexes and uniques missed by autogenerate
    op.create_index("ix_product_sku_sku", "product_sku", ["sku"], unique=True)
    op.create_index("ix_stripe_event_event_type", "stripe_event", ["event_type"], unique=False)
    op.create_index("ix_inventory_item_name_org", "inventory_item", ["organization_id", "name"], unique=True)


def downgrade():
    op.drop_index("ix_inventory_item_name_org", table_name="inventory_item")
    op.drop_index("ix_stripe_event_event_type", table_name="stripe_event")
    op.drop_index("ix_product_sku_sku", table_name="product_sku")
