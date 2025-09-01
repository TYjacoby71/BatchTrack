
#!/usr/bin/env python3
"""
Script to update all recipe URL references to use standardized naming.
"""

import os
import re
from pathlib import Path

def update_file_content(file_path, replacements):
    """Update file content with given replacements."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for old_pattern, new_pattern in replacements:
            content = re.sub(old_pattern, new_pattern, content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
            return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
    
    return False

def main():
    """Main update function."""
    # Define URL replacements
    replacements = [
        # Function name updates
        (r"url_for\('recipes\.new_recipe'", "url_for('recipes.create_recipe'"),
        
        # Template references
        (r"recipe_list\.html", "list_recipes.html"),
        (r"recipe_form\.html", "create_recipe.html"),
        
        # JavaScript URL updates
        (r"'/recipes/new'", "'/recipes/new'"),  # This stays the same
        
        # Breadcrumb updates in templates
        (r'<a href="{{ url_for\(\'recipes\.new_recipe\'\) }}"', 
         '<a href="{{ url_for(\'recipes.create_recipe\') }}"'),
    ]
    
    # Files to update
    update_patterns = [
        "app/templates/**/*.html",
        "app/blueprints/**/*.py", 
        "app/routes/**/*.py",
        "static/js/**/*.js"
    ]
    
    updated_files = 0
    for pattern in update_patterns:
        for file_path in Path('.').glob(pattern):
            if file_path.is_file():
                if update_file_content(file_path, replacements):
                    updated_files += 1
    
    print(f"\nCompleted! Updated {updated_files} files.")

if __name__ == "__main__":
    main()
