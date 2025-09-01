
#!/usr/bin/env python3
"""
Script to migrate all storage_amount/storage_unit references to capacity/capacity_unit
"""

import os
import re
import glob

def find_and_replace_in_file(file_path, replacements):
    """Find and replace patterns in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = []
        
        for old_pattern, new_pattern in replacements:
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                changes_made.append(f"  - {old_pattern} → {new_pattern}")
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
            for change in changes_made:
                print(change)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main migration function"""
    
    # Define replacement patterns
    replacements = [
        # Python/model patterns
        ('storage_amount', 'capacity'),
        ('storage_unit', 'capacity_unit'),
        
        # HTML template patterns
        ('inventory_item_storage_amount', 'inventory_item_capacity'),
        ('inventory_item_storage_unit', 'inventory_item_capacity_unit'),
        
        # JavaScript patterns
        ('storageAmount', 'capacity'),
        ('storageUnit', 'capacityUnit'),
        ('storage_amount', 'capacity'),
        ('storage_unit', 'capacity_unit'),
        
        # SQL patterns in comments or strings
        ('storage_amount', 'capacity'),
        ('storage_unit', 'capacity_unit'),
    ]
    
    # File patterns to search
    file_patterns = [
        'app/**/*.py',
        'app/**/*.html', 
        'app/**/*.js',
        'static/**/*.js',
        'templates/**/*.html',
        'services/**/*.py',
        'migrations/versions/*.py',
        '*.py'
    ]
    
    files_to_process = []
    for pattern in file_patterns:
        files_to_process.extend(glob.glob(pattern, recursive=True))
    
    # Remove duplicates and filter out this script
    files_to_process = list(set(files_to_process))
    files_to_process = [f for f in files_to_process if not f.endswith('migrate_storage_to_capacity.py')]
    
    print(f"Processing {len(files_to_process)} files...")
    print("=" * 50)
    
    updated_files = 0
    for file_path in files_to_process:
        if find_and_replace_in_file(file_path, replacements):
            updated_files += 1
    
    print("=" * 50)
    print(f"Migration complete! Updated {updated_files} files.")
    print("\nNext steps:")
    print("1. Run: flask db upgrade")
    print("2. Test the application")
    print("3. Remove this script when confirmed working")

if __name__ == '__main__':
    main()
