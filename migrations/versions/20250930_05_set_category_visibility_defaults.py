
"""Set default visibility flags for global ingredient categories

Revision ID: 20250930_5
Revises: 20250930_4
Create Date: 2025-09-30 00:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
import json
import os
import glob

# revision identifiers, used by Alembic.
revision = '20250930_5'
down_revision = '20250930_4'
branch_labels = None
depends_on = None

def upgrade():
    print("Setting visibility defaults for global ingredient categories from JSON files...")
    
    bind = op.get_bind()
    
    # Get the base path for the seeders directory
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    categories_path = os.path.join(base_path, 'app/seeders/globallist/ingredients/categories/*.json')
    
    # Process each category JSON file
    category_files = glob.glob(categories_path)
    
    for file_path in category_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            category_name = data.get('category_name')
            if not category_name:
                print(f"   ⚠️  Skipping {os.path.basename(file_path)} - no category_name")
                continue
            
            # Build update query from JSON visibility settings
            visibility_fields = [
                'show_saponification_value',
                'show_iodine_value', 
                'show_melting_point',
                'show_flash_point',
                'show_ph_value',
                'show_moisture_content',
                'show_shelf_life_months',
                'show_comedogenic_rating'
            ]
            
            # Build SET clause for fields present in JSON
            set_clauses = []
            params = {'category_name': category_name}
            
            for field in visibility_fields:
                if field in data:
                    set_clauses.append(f"{field} = :{field}")
                    params[field] = data[field]
            
            # Only update if we have visibility settings in the JSON
            if set_clauses:
                sql = f"""
                    UPDATE ingredient_category 
                    SET {', '.join(set_clauses)}
                    WHERE name = :category_name AND organization_id IS NULL
                """
                
                result = bind.execute(text(sql), params)
                if result.rowcount > 0:
                    print(f"   ✅ Updated visibility for '{category_name}' category")
                else:
                    print(f"   ⚠️  Category '{category_name}' not found in database")
            else:
                print(f"   ⚠️  No visibility settings found for '{category_name}'")
                
        except Exception as e:
            print(f"   ❌ Error processing {os.path.basename(file_path)}: {e}")
    
    print("✅ Category visibility defaults set successfully!")

def downgrade():
    print("Resetting all category visibility flags to False...")
    
    bind = op.get_bind()
    
    # Reset all visibility flags to False for global categories
    bind.execute(text("""
        UPDATE ingredient_category 
        SET show_saponification_value = FALSE,
            show_iodine_value = FALSE,
            show_melting_point = FALSE,
            show_flash_point = FALSE,
            show_ph_value = FALSE,
            show_moisture_content = FALSE,
            show_shelf_life_months = FALSE,
            show_comedogenic_rating = FALSE
        WHERE organization_id IS NULL
    """))
    
    print("✅ Category visibility flags reset!")
