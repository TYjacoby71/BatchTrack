
"""
Add visibility control fields for soap-making attributes to ingredient categories

Revision ID: 20250930_4
Revises: 20250930_3
Create Date: 2025-09-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250930_4'
down_revision = '20250930_3'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Adding visibility control fields to ingredient_category ===")
    
    # Add visibility control fields to ingredient_category
    with op.batch_alter_table('ingredient_category') as batch_op:
        batch_op.add_column(sa.Column('show_saponification_value', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_iodine_value', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_melting_point', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_flash_point', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_ph_value', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_moisture_content', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_shelf_life_months', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('show_comedogenic_rating', sa.Boolean(), default=False))
    
    print("✅ Visibility control fields added to ingredient_category")
    
    # Set default visibility for common soap-making categories
    connection = op.get_bind()
    
    # Enable soap-making fields for oil categories
    oil_categories = ['Oils', 'Oils - Liquid Fats', 'Butters - Solid Fats', 'Essential Oils']
    for category_name in oil_categories:
        connection.execute(sa.text("""
            UPDATE ingredient_category 
            SET show_saponification_value = true,
                show_iodine_value = true,
                show_comedogenic_rating = true
            WHERE name = :category_name
        """), {"category_name": category_name})
    
    # Enable pH for liquid categories
    liquid_categories = ['Liquids - Aqueous', 'Extracts - Alcohols - Solvents']
    for category_name in liquid_categories:
        connection.execute(sa.text("""
            UPDATE ingredient_category 
            SET show_ph_value = true
            WHERE name = :category_name
        """), {"category_name": category_name})
    
    # Enable melting point for solid ingredients
    solid_categories = ['Waxes', 'Butters - Solid Fats']
    for category_name in solid_categories:
        connection.execute(sa.text("""
            UPDATE ingredient_category 
            SET show_melting_point = true
            WHERE name = :category_name
        """), {"category_name": category_name})
    
    print("✅ Default visibility settings applied to common categories")


def downgrade():
    # Remove visibility control fields from ingredient_category
    try:
        with op.batch_alter_table('ingredient_category') as batch_op:
            batch_op.drop_column('show_comedogenic_rating')
            batch_op.drop_column('show_shelf_life_months')
            batch_op.drop_column('show_moisture_content')
            batch_op.drop_column('show_ph_value')
            batch_op.drop_column('show_flash_point')
            batch_op.drop_column('show_melting_point')
            batch_op.drop_column('show_iodine_value')
            batch_op.drop_column('show_saponification_value')
    except Exception:
        pass
