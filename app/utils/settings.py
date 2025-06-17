
import json
import os

def get_setting(key, default=None):
    """Get a setting from settings.json file"""
    try:
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                return settings.get(key, default)
        return default
    except:
        return default
