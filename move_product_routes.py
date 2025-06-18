
#!/usr/bin/env python3
"""
Script to move product-related route files to app/blueprints/products/
and update imports and registrations accordingly.
"""

import os
import shutil
from pathlib import Path

def move_product_routes():
    """Move product route files to blueprints/products directory"""
    
    # Files to move
    files_to_move = [
        'app/routes/product_api.py',
        'app/routes/product_inventory.py', 
        'app/routes/product_log_routes.py',
        'app/routes/product_variants.py',
        'app/routes/products.py'
    ]
    
    # Destination directory
    dest_dir = Path('app/blueprints/products')
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Move files
    for file_path in files_to_move:
        src_path = Path(file_path)
        if src_path.exists():
            dest_path = dest_dir / src_path.name
            print(f"Moving {src_path} to {dest_path}")
            shutil.move(str(src_path), str(dest_path))
        else:
            print(f"Warning: {src_path} not found")
    
    print("✅ Product route files moved successfully!")

def update_products_blueprint():
    """Update the products blueprint __init__.py to import all routes"""
    
    blueprint_init_content = '''from flask import Blueprint

products_bp = Blueprint('products', __name__, template_folder='templates')

# Import all product-related routes
from .products import products_bp as main_products_bp
from .product_variants import product_variants_bp
from .product_inventory import product_inventory_bp  
from .product_api import product_api_bp
from .product_log_routes import product_log_bp

# Register sub-blueprints
def register_product_blueprints(app):
    """Register all product-related blueprints"""
    app.register_blueprint(main_products_bp)
    app.register_blueprint(product_variants_bp)
    app.register_blueprint(product_inventory_bp)
    app.register_blueprint(product_api_bp)
    app.register_blueprint(product_log_bp)
'''
    
    init_path = Path('app/blueprints/products/__init__.py')
    with open(init_path, 'w') as f:
        f.write(blueprint_init_content)
    
    print("✅ Updated products blueprint __init__.py")

def update_app_init():
    """Update app/__init__.py to use the new blueprint structure"""
    
    # Read current app/__init__.py
    app_init_path = Path('app/__init__.py')
    with open(app_init_path, 'r') as f:
        content = f.read()
    
    # Remove old product route imports and registrations
    lines_to_remove = [
        'from .routes.products import products_bp',
        'from .routes.product_variants import product_variants_bp',
        'from .routes.product_inventory import product_inventory_bp',
        'from .routes.product_api import product_api_bp',
        'from .routes.product_log_routes import product_log_bp',
        'app.register_blueprint(products_bp)',
        'app.register_blueprint(product_variants_bp)',
        'app.register_blueprint(product_inventory_bp)',
        'app.register_blueprint(product_api_bp)',
        'app.register_blueprint(product_log_bp)'
    ]
    
    # Remove old imports and registrations
    for line_to_remove in lines_to_remove:
        content = content.replace(line_to_remove, '')
    
    # Add new products blueprint registration
    if 'from .blueprints.products import register_product_blueprints' not in content:
        # Find where other blueprints are imported
        import_section = content.find('from .blueprints.products import products_bp')
        if import_section != -1:
            content = content.replace(
                'from .blueprints.products import products_bp',
                'from .blueprints.products import products_bp, register_product_blueprints'
            )
            
            # Find where products_bp is registered and add the function call
            registration_section = content.find('app.register_blueprint(products_bp')
            if registration_section != -1:
                # Add the registration function call
                content = content.replace(
                    'app.register_blueprint(products_bp, url_prefix=\'/products\')',
                    'app.register_blueprint(products_bp, url_prefix=\'/products\')\n    register_product_blueprints(app)'
                )
    
    # Write updated content
    with open(app_init_path, 'w') as f:
        f.write(content)
    
    print("✅ Updated app/__init__.py")

def fix_relative_imports():
    """Fix relative imports in moved files"""
    
    moved_files = [
        'app/blueprints/products/product_api.py',
        'app/blueprints/products/product_inventory.py',
        'app/blueprints/products/product_log_routes.py', 
        'app/blueprints/products/product_variants.py',
        'app/blueprints/products/products.py'
    ]
    
    for file_path in moved_files:
        path = Path(file_path)
        if path.exists():
            with open(path, 'r') as f:
                content = f.read()
            
            # Fix relative imports
            content = content.replace('from ..models', 'from ...models')
            content = content.replace('from ..services', 'from ...services')
            content = content.replace('from ..utils', 'from ...utils')
            content = content.replace('from ..filters', 'from ...filters')
            
            with open(path, 'w') as f:
                f.write(content)
            
            print(f"✅ Fixed imports in {file_path}")

if __name__ == '__main__':
    print("🚀 Moving product routes to blueprints/products...")
    
    move_product_routes()
    update_products_blueprint()
    update_app_init()
    fix_relative_imports()
    
    print("\n🎉 Migration complete!")
    print("Product routes have been moved to app/blueprints/products/")
    print("Run the Flask app to test the changes.")
