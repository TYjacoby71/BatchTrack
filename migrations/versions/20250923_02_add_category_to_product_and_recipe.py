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
    """Ensure 'Uncategorized' exists and return its id"""
    # First try to find existing uncategorized category
    result = conn.execute(sa.text("SELECT id FROM product_category WHERE lower(name) = lower(:n)"), {"n": "Uncategorized"}).fetchone()
    if result:
        print(f"Found existing Uncategorized category with ID: {result[0]}")
        return result[0]
    
    # Create it if it doesn't exist
    print("Creating Uncategorized product category...")
    conn.execute(sa.text("INSERT INTO product_category (name, is_typically_portioned) VALUES (:n, false)"), {"n": "Uncategorized"})
    result = conn.execute(sa.text("SELECT id FROM product_category WHERE lower(name) = lower(:n)"), {"n": "Uncategorized"}).fetchone()
    print(f"Created Uncategorized category with ID: {result[0]}")
    return result[0]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    print("Starting product and recipe category migration...")

    # Add nullable columns first
    if 'product' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('product')]
        if 'category_id' not in columns:
            print("Adding category_id column to product table...")
            with op.batch_alter_table('product') as batch_op:
                batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        else:
            print("category_id column already exists in product table")
            
    if 'recipe' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('recipe')]
        if 'category_id' not in columns:
            print("Adding category_id column to recipe table...")
            with op.batch_alter_table('recipe') as batch_op:
                batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        else:
            print("category_id column already exists in recipe table")

    # Ensure Uncategorized category exists and get its ID
    uncategorized_id = _get_uncategorized_id(bind)
    
    # Backfill products
    if 'product' in inspector.get_table_names():
        print("Backfilling product category_id values...")
        result = bind.execute(sa.text("SELECT COUNT(*) FROM product WHERE category_id IS NULL"))
        null_count = result.fetchone()[0]
        print(f"Found {null_count} products with NULL category_id")
        
        if null_count > 0:
            bind.execute(sa.text("UPDATE product SET category_id = :cid WHERE category_id IS NULL"), {"cid": uncategorized_id})
            print(f"Updated {null_count} products to use Uncategorized category")

    # Backfill recipes
    if 'recipe' in inspector.get_table_names():
        print("Backfilling recipe category_id values...")
        result = bind.execute(sa.text("SELECT COUNT(*) FROM recipe WHERE category_id IS NULL"))
        null_count = result.fetchone()[0]
        print(f"Found {null_count} recipes with NULL category_id")
        
        if null_count > 0:
            bind.execute(sa.text("UPDATE recipe SET category_id = :cid WHERE category_id IS NULL"), {"cid": uncategorized_id})
            print(f"Updated {null_count} recipes to use Uncategorized category")

    # Verify no NULL values remain before setting NOT NULL
    product_nulls = bind.execute(sa.text("SELECT COUNT(*) FROM product WHERE category_id IS NULL")).fetchone()[0] if 'product' in inspector.get_table_names() else 0
    recipe_nulls = bind.execute(sa.text("SELECT COUNT(*) FROM recipe WHERE category_id IS NULL")).fetchone()[0] if 'recipe' in inspector.get_table_names() else 0
    
    if product_nulls > 0 or recipe_nulls > 0:
        raise Exception(f"Still have NULL category_id values: {product_nulls} products, {recipe_nulls} recipes")

    # Check existing constraints before adding new ones
    def constraint_exists(table_name, constraint_name):
        try:
            constraints = inspector.get_foreign_keys(table_name)
            return any(fk.get('name') == constraint_name for fk in constraints)
        except Exception:
            return False

    def index_exists(table_name, index_name):
        try:
            indexes = inspector.get_indexes(table_name)
            return any(idx.get('name') == index_name for idx in indexes)
        except Exception:
            return False

    # Add foreign keys, indexes, and set NOT NULL
    if 'product' in inspector.get_table_names():
        print("Adding constraints to product table...")
        with op.batch_alter_table('product') as batch_op:
            # Only create foreign key if it doesn't exist
            if not constraint_exists('product', 'fk_product_category'):
                try:
                    batch_op.create_foreign_key('fk_product_category', 'product_category', ['category_id'], ['id'])
                    print("Created foreign key fk_product_category")
                except Exception as e:
                    print(f"Note: Could not create foreign key for product: {e}")
            else:
                print("Foreign key fk_product_category already exists")
            
            # Only create index if it doesn't exist
            if not index_exists('product', 'ix_product_category_id'):
                try:
                    batch_op.create_index('ix_product_category_id', ['category_id'])
                    print("Created index ix_product_category_id")
                except Exception as e:
                    print(f"Note: Could not create index for product: {e}")
            else:
                print("Index ix_product_category_id already exists")
                
            batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)
            print("Set product.category_id to NOT NULL")

    if 'recipe' in inspector.get_table_names():
        print("Adding constraints to recipe table...")
        with op.batch_alter_table('recipe') as batch_op:
            # Only create foreign key if it doesn't exist
            if not constraint_exists('recipe', 'fk_recipe_category'):
                try:
                    batch_op.create_foreign_key('fk_recipe_category', 'product_category', ['category_id'], ['id'])
                    print("Created foreign key fk_recipe_category")
                except Exception as e:
                    print(f"Note: Could not create foreign key for recipe: {e}")
            else:
                print("Foreign key fk_recipe_category already exists")
                
            # Only create index if it doesn't exist
            if not index_exists('recipe', 'ix_recipe_category_id'):
                try:
                    batch_op.create_index('ix_recipe_category_id', ['category_id'])
                    print("Created index ix_recipe_category_id")
                except Exception as e:
                    print(f"Note: Could not create index for recipe: {e}")
            else:
                print("Index ix_recipe_category_id already exists")
                
            batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)
            print("Set recipe.category_id to NOT NULL")

    print("✅ Product and recipe category migration completed successfully!")


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

