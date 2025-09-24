"""
Add category_id to product and recipe, backfill to Uncategorized, set NOT NULL

Revision ID: 20250923_02
Revises: 20250923_01
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250923_02'
down_revision = '20250923_01'
branch_labels = None
depends_on = None


def _get_uncategorized_id(conn):
    # Ensure 'Uncategorized' exists and return its id
    result = conn.execute(sa.text("SELECT id FROM product_category WHERE lower(name) = lower(:n)"), {"n": "Uncategorized"}).fetchone()
    if result:
        return result[0]
    conn.execute(sa.text("INSERT INTO product_category (name, is_typically_portioned) VALUES (:n, false)"), {"n": "Uncategorized"})
    result = conn.execute(sa.text("SELECT id FROM product_category WHERE lower(name) = lower(:n)"), {"n": "Uncategorized"}).fetchone()
    return result[0]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Add nullable columns first
    if 'product' in inspector.get_table_names():
        with op.batch_alter_table('product') as batch_op:
            batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
    if 'recipe' in inspector.get_table_names():
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))

    # Backfill to Uncategorized
    uncategorized_id = _get_uncategorized_id(bind)
    try:
        op.execute(sa.text("UPDATE product SET category_id = :cid WHERE category_id IS NULL"), {"cid": uncategorized_id})
    except Exception:
        pass
    try:
        op.execute(sa.text("UPDATE recipe SET category_id = :cid WHERE category_id IS NULL"), {"cid": uncategorized_id})
    except Exception:
        pass

    # Add FKs and indexes, then set NOT NULL
    with op.batch_alter_table('product') as batch_op:
        try:
            batch_op.create_foreign_key('fk_product_category', 'product_category', ['category_id'], ['id'])
        except Exception:
            pass
        batch_op.create_index('ix_product_category_id', ['category_id'])
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('recipe') as batch_op:
        try:
            batch_op.create_foreign_key('fk_recipe_category', 'product_category', ['category_id'], ['id'])
        except Exception:
            pass
        batch_op.create_index('ix_recipe_category_id', ['category_id'])
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)


def downgrade():
    # Make columns nullable again and drop FKs
    try:
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=True)
            try:
                batch_op.drop_constraint('fk_recipe_category', type_='foreignkey')
            except Exception:
                pass
            try:
                batch_op.drop_index('ix_recipe_category_id')
            except Exception:
                pass
            batch_op.drop_column('category_id')
    except Exception:
        pass

    try:
        with op.batch_alter_table('product') as batch_op:
            batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=True)
            try:
                batch_op.drop_constraint('fk_product_category', type_='foreignkey')
            except Exception:
                pass
            try:
                batch_op.drop_index('ix_product_category_id')
            except Exception:
                pass
            batch_op.drop_column('category_id')
    except Exception:
        pass

