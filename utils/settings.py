
import json
import os
from flask import current_app

DEFAULT_SETTINGS = {
    "low_stock_threshold": 5,
    "per_page": 20,
    "enable_csv_export": True,
    "alerts": {
        "low_stock_threshold": 5,
        "notification_type": "dashboard",
        "show_inventory_refund": True
    },
    "batch": {
        "auto_generate_labels": True,
        "require_containers": False,
        "default_scale": 1.0
    },
    "inventory": {
        "enable_fifo": True,
        "track_expiration": True,
        "auto_archive_expired": False
    }
}

def get_setting(key, default=None):
    """Get a setting value with dot notation support"""
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = DEFAULT_SETTINGS.copy()
        save_settings(settings)
    
    # Support dot notation (e.g., 'alerts.show_inventory_refund')
    keys = key.split('.')
    value = settings
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value

def save_settings(settings):
    """Save settings to file"""
    with open('settings.json', 'w') as f:
        json.dump(settings, f, indent=2)

def update_setting(key, value):
    """Update a specific setting"""
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = DEFAULT_SETTINGS.copy()
    
    # Support dot notation
    keys = key.split('.')
    current = settings
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value
    
    save_settings(settings)
    return True
