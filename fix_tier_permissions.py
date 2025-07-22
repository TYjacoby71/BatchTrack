
import json
import os
from app.blueprints.developer.subscription_tiers import get_default_tier_permissions

def fix_tier_permissions():
    """Fix subscription tier permissions"""
    
    # Get default permissions
    default_permissions = get_default_tier_permissions()
    
    # Load existing config
    config_file = 'subscription_tiers.json'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Update each tier with correct permissions
    for tier_key, permissions in default_permissions.items():
        if tier_key not in config:
            config[tier_key] = {}
        
        config[tier_key]['permissions'] = permissions
        
        # Ensure other required fields exist
        if 'name' not in config[tier_key]:
            config[tier_key]['name'] = tier_key.title() + ' Tier'
        if 'user_limit' not in config[tier_key]:
            limits = {
                'free': 1,
                'solo': 5, 
                'team': 15,
                'enterprise': -1,
                'exempt': -1
            }
            config[tier_key]['user_limit'] = limits.get(tier_key, 1)
        if 'is_customer_facing' not in config[tier_key]:
            config[tier_key]['is_customer_facing'] = tier_key != 'exempt'
        if 'is_available' not in config[tier_key]:
            config[tier_key]['is_available'] = True
    
    # Save updated config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Updated {config_file} with correct tier permissions")
    print(f"Solo tier now has {len(config['solo']['permissions'])} permissions")

if __name__ == '__main__':
    fix_tier_permissions()
