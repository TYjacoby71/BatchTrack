
#!/usr/bin/env python3
"""
Automated import fixer for factory pattern migration
"""
import os
import re
from pathlib import Path

def fix_blueprint_exports():
    """Fix blueprint name exports to match expected imports"""
    fixes = [
        ('app/routes/fault_log_routes.py', 'faults_bp', 'fault_log_bp'),
        ('app/routes/product_log_routes.py', 'product_log_bp', 'product_log_bp'),
        ('app/routes/bulk_stock_routes.py', 'bulk_stock_bp', 'bulk_stock_bp'),
        ('app/routes/tag_manager_routes.py', 'tag_bp', 'tag_manager_bp'),
        ('app/routes/admin_routes.py', 'admin_bp', 'admin_bp'),
        ('app/routes/app_routes.py', 'app_routes_bp', 'app_routes_bp'),
    ]
    
    for file_path, old_name, new_name in fixes:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Replace blueprint definition and all references
            content = re.sub(f'{old_name} = Blueprint', f'{new_name} = Blueprint', content)
            content = re.sub(f'@{old_name}\\.', f'@{new_name}.', content)
            
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"Fixed {file_path}: {old_name} -> {new_name}")

def fix_imports_in_app_init():
    """Fix the imports in app/__init__.py to match actual blueprint names"""
    app_init_path = 'app/__init__.py'
    if not os.path.exists(app_init_path):
        return
    
    with open(app_init_path, 'r') as f:
        content = f.read()
    
    # Fix route imports
    import_fixes = [
        ('from .routes.fault_log_routes import fault_log_bp', 'from .routes.fault_log_routes import fault_log_bp'),
        ('from .routes.product_log_routes import product_log_bp', 'from .routes.product_log_routes import product_log_bp'),
        ('from .routes.bulk_stock_routes import bulk_stock_bp', 'from .routes.bulk_stock_routes import bulk_stock_bp'),
        ('from .routes.tag_manager_routes import tag_manager_bp', 'from .routes.tag_manager_routes import tag_manager_bp'),
        ('from .routes.admin_routes import admin_bp', 'from .routes.admin_routes import admin_bp'),
        ('from .routes.app_routes import app_routes_bp', 'from .routes.app_routes import app_routes_bp'),
    ]
    
    # Add missing imports if they don't exist
    if 'fault_log_bp' not in content:
        # Add the imports section
        import_section = '''
    # Route blueprints
    from .routes.fault_log_routes import fault_log_bp
    from .routes.product_log_routes import product_log_bp
    from .routes.bulk_stock_routes import bulk_stock_bp
    from .routes.tag_manager_routes import tag_manager_bp
    from .routes.admin_routes import admin_bp
    from .routes.app_routes import app_routes_bp
    
    # Product route modules
    from .routes.products import products_bp
    from .routes.product_variants import product_variants_bp
    from .routes.product_inventory import product_inventory_bp
    from .routes.product_api import product_api_bp
    '''
        
        # Find the existing blueprint imports and add after them
        content = re.sub(
            r'(from \.blueprints\.api import api_bp)',
            r'\1' + import_section,
            content
        )
        
        # Add registrations
        registration_section = '''
    
    # Register route blueprints
    app.register_blueprint(fault_log_bp, url_prefix='/logs')
    app.register_blueprint(product_log_bp, url_prefix='/product-logs')
    app.register_blueprint(bulk_stock_bp, url_prefix='/stock')
    app.register_blueprint(tag_manager_bp, url_prefix='/tags')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(app_routes_bp)
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(product_variants_bp, url_prefix='/products')
    app.register_blueprint(product_inventory_bp, url_prefix='/products')
    app.register_blueprint(product_api_bp, url_prefix='/api/products')
    '''
        
        content = re.sub(
            r'(app\.register_blueprint\(api_bp, url_prefix=\'/api\'\))',
            r'\1' + registration_section,
            content
        )
    
    with open(app_init_path, 'w') as f:
        f.write(content)
    print(f"Updated {app_init_path}")

def fix_relative_imports():
    """Fix relative imports in all Python files"""
    app_files = list(Path('app').rglob('*.py'))
    
    for file_path in app_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Common import fixes for files in app/
            fixes = [
                (r'^from models import (.+)$', r'from ..models import \1'),
                (r'^from services\.(.+) import (.+)$', r'from ..services.\1 import \2'),
                (r'^from utils import (.+)$', r'from ..utils import \1'),
                (r'^from utils\.(.+) import (.+)$', r'from ..utils.\1 import \2'),
                (r'^from fault_log_utils import (.+)$', r'from ...fault_log_utils import \1'),
                (r'^import models$', 'from .. import models'),
            ]
            
            for pattern, replacement in fixes:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            
            if content != original_content:
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"Fixed imports in {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

def main():
    print("🔧 Running automated import fixes...")
    
    print("\n1. Fixing blueprint exports...")
    fix_blueprint_exports()
    
    print("\n2. Updating app/__init__.py...")
    fix_imports_in_app_init()
    
    print("\n3. Fixing relative imports...")
    fix_relative_imports()
    
    print("\n✅ Automated fixes complete!")
    print("Try running the app again with: python run.py")

if __name__ == '__main__':
    main()
