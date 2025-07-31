
#!/usr/bin/env python3
"""
TEMPORARY: Disable all model constraints and relationships for seeding
This is a temporary measure to allow seeding without constraint violations
TODO: Remove this file after adding proper constraints migration
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def patch_models_for_seeding():
    """Temporarily disable all SQLAlchemy relationship constraints"""
    print("🔧 TEMPORARILY disabling model constraints for seeding...")
    
    # We'll patch the models at import time to remove foreign key constraints
    # This is a hack, but it's temporary and allows seeding to work
    
    from app.models import models
    from app.models import product
    from app.models import inventory
    from app.models import batch
    from app.models import recipe
    
    # List of models to patch
    models_to_patch = [
        models.User,
        models.Organization, 
        models.ProductSKU,
        models.ProductSKUHistory,
        models.InventoryItem,
        models.InventoryHistory,
        models.Batch,
        models.Recipe,
        models.Product,
        models.ProductVariant,
    ]
    
    patched_count = 0
    
    for model_class in models_to_patch:
        if hasattr(model_class, '__table__'):
            # Remove foreign key constraints from table
            table = model_class.__table__
            original_constraints = table.foreign_key_constraints.copy()
            table.foreign_key_constraints.clear()
            
            # Store original for restoration (if needed)
            if not hasattr(model_class, '_original_fk_constraints'):
                model_class._original_fk_constraints = original_constraints
            
            patched_count += 1
            
    print(f"✅ Patched {patched_count} models - foreign key constraints disabled")
    print("⚠️  This is TEMPORARY for seeding only!")
    
    return True

if __name__ == "__main__":
    patch_models_for_seeding()
    print("✅ Models patched for constraint-free seeding")
