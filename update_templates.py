
#!/usr/bin/env python3
"""
Bulk Template Updater
Finds and updates all template files to use safe_url_for instead of url_for
"""

import os
import re
from pathlib import Path

def find_template_files(directory="app/templates"):
    """Find all HTML template files"""
    template_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))
    return template_files

def update_url_for_calls(content):
    """Update url_for calls to safe_url_for in template content"""
    # Pattern to match url_for calls
    pattern = r'\{\{\s*url_for\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*(?:,\s*([^}]*))?\s*\)\s*\}\}'
    
    def replace_url_for(match):
        endpoint = match.group(1)
        params = match.group(2) if match.group(2) else ""
        
        if params:
            return f"{{{{ safe_url_for('{endpoint}', {params}) }}}}"
        else:
            return f"{{{{ safe_url_for('{endpoint}') }}}}"
    
    updated_content = re.sub(pattern, replace_url_for, content)
    return updated_content

def update_template_file(file_path):
    """Update a single template file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        updated_content = update_url_for_calls(original_content)
        
        if original_content != updated_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"✅ Updated: {file_path}")
            return True
        else:
            print(f"⏭️  No changes needed: {file_path}")
            return False
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return False

def main():
    """Main function to update all templates"""
    print("🚀 Starting bulk template update...")
    
    template_files = find_template_files()
    print(f"Found {len(template_files)} template files")
    
    updated_count = 0
    for file_path in template_files:
        if update_template_file(file_path):
            updated_count += 1
    
    print(f"\n✅ Update complete!")
    print(f"📊 Updated {updated_count} out of {len(template_files)} template files")
    
    # Show some common endpoints that might need manual attention
    print("\n📋 Common endpoints that might need manual verification:")
    common_endpoints = [
        'products.product_list',
        'batches.list_batches', 
        'inventory.list_inventory',
        'recipes.list_recipes',
        'admin.cleanup_tools'
    ]
    
    for endpoint in common_endpoints:
        print(f"  - {endpoint}")

if __name__ == '__main__':
    main()
