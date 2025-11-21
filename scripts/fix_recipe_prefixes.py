
#!/usr/bin/env python3
"""
Script to fix existing recipes with missing or invalid label prefixes.

This script will:
1. Find recipes with empty/None label_prefix values
2. Generate proper prefixes using the recipe name
3. Handle variations properly with V1, V2, etc. suffixes
4. Update the database
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Recipe
from app.utils.code_generator import generate_recipe_prefix
from sqlalchemy import func

def fix_recipe_prefixes():
    """Fix all recipes with missing or invalid label prefixes"""
    
    app = create_app()
    
    with app.app_context():
        print("🔧 Starting recipe prefix fix...")
        
        # Find recipes with missing or problematic prefixes
        problematic_recipes = Recipe.query.filter(
            db.or_(
                Recipe.label_prefix.is_(None),
                Recipe.label_prefix == '',
                Recipe.label_prefix == 'NONE',
                Recipe.label_prefix == 'None'
            )
        ).all()
        
        if not problematic_recipes:
            print("✅ No recipes found with missing prefixes!")
            return
        
        print(f"📋 Found {len(problematic_recipes)} recipes needing prefix fixes")
        
        fixed_count = 0
        variation_count = 0
        
        for recipe in problematic_recipes:
            print(f"\n🔍 Processing recipe: {recipe.name} (ID: {recipe.id})")
            
            # Generate base prefix from recipe name
            if recipe.parent_recipe_id:
                # This is a variation - handle specially
                parent_recipe = db.session.get(Recipe, recipe.parent_recipe_id)
                if parent_recipe and parent_recipe.label_prefix and parent_recipe.label_prefix not in ['NONE', 'None', '']:
                    # Use parent prefix with variation suffix
                    base_prefix = parent_recipe.label_prefix
                    # Count existing variations with same base prefix
                    existing_variations = Recipe.query.filter(
                        Recipe.parent_recipe_id == recipe.parent_recipe_id,
                        Recipe.label_prefix.like(f"{base_prefix}%"),
                        Recipe.id != recipe.id  # Don't count this recipe
                    ).count()
                    new_prefix = f"{base_prefix}V{existing_variations + 1}"
                    variation_count += 1
                    print(f"   📝 Variation recipe - using parent prefix: {new_prefix}")
                else:
                    # Parent doesn't have good prefix either, generate fresh one
                    new_prefix = generate_recipe_prefix(recipe.name)
                    print(f"   📝 Parent has bad prefix too, generating fresh: {new_prefix}")
            else:
                # Regular recipe - generate from name
                new_prefix = generate_recipe_prefix(recipe.name)
                print(f"   📝 Generated prefix from name: {new_prefix}")
            
            # Check for conflicts with existing recipes
            conflict_check = Recipe.query.filter(
                Recipe.label_prefix == new_prefix,
                Recipe.id != recipe.id
            ).first()
            
            if conflict_check:
                # Add number suffix to make unique
                counter = 1
                while True:
                    test_prefix = f"{new_prefix}{counter}"
                    if not Recipe.query.filter(
                        Recipe.label_prefix == test_prefix,
                        Recipe.id != recipe.id
                    ).first():
                        new_prefix = test_prefix
                        break
                    counter += 1
                print(f"   ⚠️  Conflict found, using: {new_prefix}")
            
            # Update the recipe
            old_prefix = recipe.label_prefix
            recipe.label_prefix = new_prefix
            
            try:
                db.session.commit()
                print(f"   ✅ Updated: '{old_prefix}' → '{new_prefix}'")
                fixed_count += 1
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Error updating recipe {recipe.id}: {e}")
                continue
        
        print(f"\n🎉 Prefix fix complete!")
        print(f"   📊 Fixed {fixed_count} recipes")
        print(f"   📊 {variation_count} were variations")
        print(f"   📊 {len(problematic_recipes) - fixed_count} failed to update")
        
        # Show sample of what was fixed
        if fixed_count > 0:
            print(f"\n📋 Sample of fixes:")
            updated_recipes = Recipe.query.filter(
                Recipe.label_prefix.notin_(['NONE', 'None', '', None])
            ).limit(5).all()
            
            for recipe in updated_recipes:
                print(f"   • {recipe.name} → {recipe.label_prefix}")

if __name__ == "__main__":
    fix_recipe_prefixes()
