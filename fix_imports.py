
#!/usr/bin/env python3
"""
Script to find and fix naked model imports and other import issues
after factory pattern migration
"""

import os
import re
from pathlib import Path

def find_python_files(directory):
    """Find all Python files in directory and subdirectories"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        if any(skip in root for skip in ['__pycache__', '.git', 'migrations/versions']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def fix_imports_in_file(file_path):
    """Fix import statements in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return False
    
    original_content = content
    changes_made = []
    
    # Determine the relative path context
    rel_path = os.path.relpath(file_path)
    in_app_package = rel_path.startswith('app/')
    
    # Fix common import patterns
    if in_app_package:
        # Files inside app/ package should use relative imports
        
        # Fix naked model imports
        patterns_to_fix = [
            # from models import ... -> from ..models import ... or from .models import ...
            (r'^from models import (.+)$', r'from ..models import \1'),
            # from services. -> from ..services. or from .services.
            (r'^from services\.(.+) import (.+)$', r'from ..services.\1 import \2'),
            # from utils import -> from ..utils import or from .utils import
            (r'^from utils import (.+)$', r'from ..utils import \1'),
            (r'^from utils\.(.+) import (.+)$', r'from ..utils.\1 import \2'),
            # from blueprints. -> from . or from ..blueprints.
            (r'^from blueprints\.(.+) import (.+)$', r'from ..\1 import \2'),
            # import models -> from .. import models or from . import models
            (r'^import models$', 'from .. import models'),
        ]
        
        # Specific fixes for blueprint files
        if 'blueprints' in rel_path:
            # For blueprint route files, adjust relative imports
            if rel_path.count('/') >= 3:  # app/blueprints/something/routes.py
                patterns_to_fix = [
                    (r'^from models import (.+)$', r'from ...models import \1'),
                    (r'^from services\.(.+) import (.+)$', r'from ...services.\1 import \2'),
                    (r'^from utils import (.+)$', r'from ...utils import \1'),
                    (r'^from utils\.(.+) import (.+)$', r'from ...utils.\1 import \2'),
                ]
    else:
        # Files outside app/ package should import from app
        patterns_to_fix = [
            (r'^from models import (.+)$', r'from app.models import \1'),
            (r'^from services\.(.+) import (.+)$', r'from app.services.\1 import \2'),
            (r'^from utils import (.+)$', r'from app.utils import \1'),
            (r'^from utils\.(.+) import (.+)$', r'from app.utils.\1 import \2'),
            (r'^import models$', 'from app import models'),
        ]
    
    # Apply the fixes
    for pattern, replacement in patterns_to_fix:
        old_content = content
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        if content != old_content:
            changes_made.append(f"  - {pattern} -> {replacement}")
    
    # Special case: Fix the table conflict issue in models.py
    if file_path.endswith('models.py') and 'Table \'organization\' is already defined' in str(original_content):
        # This error suggests we have duplicate model definitions
        # Check if this is the root models.py that should be removed
        if not in_app_package and os.path.exists('app/models/models.py'):
            print(f"⚠️  Found duplicate models.py at {file_path} - should be removed")
            return False
    
    # Write back if changes were made
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed imports in {file_path}")
            for change in changes_made:
                print(change)
            return True
        except Exception as e:
            print(f"❌ Error writing {file_path}: {e}")
            return False
    
    return False

def remove_duplicate_files():
    """Remove duplicate files that conflict with app/ structure"""
    files_to_check = [
        'models.py',  # Should only exist in app/models/
        'utils.py',   # Check if conflicts with app/utils/
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            app_equivalent = f'app/{file_path}' if file_path != 'models.py' else 'app/models/models.py'
            if os.path.exists(app_equivalent):
                print(f"⚠️  Found duplicate: {file_path} (app version exists at {app_equivalent})")
                # Don't auto-delete, just warn
                print(f"   Consider removing {file_path} to avoid conflicts")

def main():
    """Main function to fix all imports"""
    print("🔧 Starting import fixes for factory pattern migration...")
    
    # Find all Python files
    python_files = find_python_files('.')
    
    print(f"📁 Found {len(python_files)} Python files to check")
    
    fixed_count = 0
    
    # Check for duplicate files first
    print("\n1. Checking for duplicate files...")
    remove_duplicate_files()
    
    print("\n2. Fixing imports...")
    for file_path in python_files:
        if fix_imports_in_file(file_path):
            fixed_count += 1
    
    print(f"\n✅ Import fixing complete!")
    print(f"📊 Fixed imports in {fixed_count} files")
    
    # Special handling for known problematic imports
    print("\n3. Checking for remaining issues...")
    
    # Check blueprints that import from old locations
    problematic_files = [
        'app/blueprints/batches/routes.py',
        'blueprints/inventory/routes.py',  # This one is still in old location
    ]
    
    for file_path in problematic_files:
        if os.path.exists(file_path):
            print(f"🔍 Manual review needed: {file_path}")

if __name__ == '__main__':
    main()
