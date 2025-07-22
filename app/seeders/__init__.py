
"""
Seeders package for database initialization
"""
from .unit_seeder import seed_units
from .ingredient_category_seeder import seed_categories
from .user_seeder import seed_users
from .consolidated_permission_seeder import seed_consolidated_permissions
from .subscription_seeder import seed_subscriptions

# Add alias for backward compatibility
seed_ingredient_categories = seed_categories

__all__ = [
    'seed_units', 
    'seed_categories', 
    'seed_users', 
    'seed_consolidated_permissions',
    'seed_subscriptions',
    'seed_ingredient_categories'
]
