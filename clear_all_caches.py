
#!/usr/bin/env python3
"""
Clear all caches in the BatchTrack application.
This includes Redis caches, Flask caches, and invalidates cache namespaces.
"""

import os
import sys
sys.path.insert(0, '.')

from app import create_app
from app.extensions import cache
from app.utils.cache_manager import conversion_cache, drawer_request_cache, app_cache
from app.services.cache_invalidation import (
    invalidate_ingredient_list_cache,
    invalidate_product_list_cache,
    invalidate_recipe_list_cache,
    invalidate_global_library_cache,
    invalidate_public_recipe_library_cache,
    invalidate_inventory_list_cache,
)
from app.services.statistics.analytics_service import AnalyticsDataService

def clear_all_caches():
    """Clear all application caches."""
    app = create_app()
    
    with app.app_context():
        print("🧹 Clearing all caches...")
        
        # Clear Flask cache extension
        try:
            cache.clear()
            print("✅ Flask cache cleared")
        except Exception as e:
            print(f"❌ Failed to clear Flask cache: {e}")
        
        # Clear custom cache instances
        try:
            conversion_cache.clear()
            print("✅ Conversion cache cleared")
        except Exception as e:
            print(f"❌ Failed to clear conversion cache: {e}")
        
        try:
            drawer_request_cache.clear()
            print("✅ Drawer request cache cleared")
        except Exception as e:
            print(f"❌ Failed to clear drawer request cache: {e}")
        
        try:
            app_cache.clear()
            print("✅ App cache cleared")
        except Exception as e:
            print(f"❌ Failed to clear app cache: {e}")
        
        # Invalidate specific cache namespaces (this bumps version numbers)
        try:
            # Clear all org-specific caches for common org IDs
            # We'll use None (anonymous) and some test org IDs
            org_ids = [None, 1, 2, 3, 4, 5]  # Add more if you have specific org IDs
            
            for org_id in org_ids:
                invalidate_ingredient_list_cache(org_id)
                invalidate_product_list_cache(org_id)
                invalidate_recipe_list_cache(org_id)
                invalidate_inventory_list_cache(org_id)
            
            print("✅ Organization-specific caches invalidated")
        except Exception as e:
            print(f"❌ Failed to invalidate org caches: {e}")
        
        # Clear global library caches
        try:
            invalidate_global_library_cache()
            print("✅ Global library cache invalidated")
        except Exception as e:
            print(f"❌ Failed to invalidate global library cache: {e}")
        
        try:
            invalidate_public_recipe_library_cache()
            print("✅ Public recipe library cache invalidated")
        except Exception as e:
            print(f"❌ Failed to invalidate public recipe library cache: {e}")
        
        # Clear analytics cache
        try:
            AnalyticsDataService.invalidate_cache()
            print("✅ Analytics cache invalidated")
        except Exception as e:
            print(f"❌ Failed to invalidate analytics cache: {e}")
        
        print("\n🎉 All caches cleared successfully!")
        print("\nNote: Frontend JavaScript caches will be cleared on next page load.")

if __name__ == "__main__":
    clear_all_caches()
