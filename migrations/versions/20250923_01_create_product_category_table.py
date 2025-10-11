"""Create product_category table

Revision ID: 20250923_01
Revises: 20250922_02
Create Date: 2025-09-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from migrations.postgres_helpers import table_exists, safe_create_index


# revision identifiers, used by Alembic.
revision = '20250923_01'
down_revision = '20250922_02'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Creating product_category table ===")

    # Create product_category table if it doesn't exist
    if not table_exists('product_category'):
        print("Creating product_category table...")
        try:
            op.create_table('product_category',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('name', sa.String(length=100), nullable=False),
                sa.Column('description', sa.Text(), nullable=True),
                sa.Column('is_typically_portioned', sa.Boolean(), nullable=False, default=False, server_default='false'),
                sa.Column('organization_id', sa.Integer(), nullable=False),
                sa.Column('created_at', sa.DateTime(), nullable=True),
                sa.Column('updated_at', sa.DateTime(), nullable=True),
                sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
                sa.PrimaryKeyConstraint('id')
            )
            print("✅ Created product_category table")
        except Exception as e:
            print(f"⚠️  Error creating product_category table: {e}")
    else:
        print("✅ product_category table already exists")

    # Create indexes
    safe_create_index('ix_product_category_organization_id', 'product_category', ['organization_id'])
    safe_create_index('ix_product_category_name', 'product_category', ['name'])

    print("✅ Product category migration completed")


def downgrade():
    print("=== Dropping product_category table ===")

    # Drop indexes first
    try:
        op.drop_index('ix_product_category_name', table_name='product_category')
        print("Dropped ix_product_category_name")
    except Exception as e:
        print(f"⚠️  Could not drop ix_product_category_name: {e}")

    try:
        op.drop_index('ix_product_category_organization_id', table_name='product_category')
        print("Dropped ix_product_category_organization_id")
    except Exception as e:
        print(f"⚠️  Could not drop ix_product_category_organization_id: {e}")

    # Drop table
    if table_exists('product_category'):
        try:
            op.drop_table('product_category')
            print("✅ Dropped product_category table")
        except Exception as e:
            print(f"⚠️  Could not drop product_category table: {e}")
    else:
        print("product_category table doesn't exist")

    print("✅ Downgrade completed")