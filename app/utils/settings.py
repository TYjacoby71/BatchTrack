import os
from typing import Any, Dict

from .json_store import read_json_file, write_json_file

class SettingsService:
    """Service for managing application settings"""

    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file"""
        self._settings = read_json_file(self.settings_file, default={}) or {}
        return self._settings

    def save_settings(self) -> bool:
        """Save settings to file"""
        try:
            write_json_file(self.settings_file, self._settings)
            return True
        except OSError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Set a setting value"""
        self._settings[key] = value
        return self.save_settings()

    def get_all(self) -> Dict[str, Any]:
        """Get all settings"""
        return self._settings.copy()

    def update_multiple(self, settings: Dict[str, Any]) -> bool:
        """Update multiple settings at once"""
        self._settings.update(settings)
        return self.save_settings()

    def delete(self, key: str) -> bool:
        """Delete a setting"""
        if key in self._settings:
            del self._settings[key]
            return self.save_settings()
        return False

# Alias for backward compatibility
SettingsManager = SettingsService

def get_setting(key, default=None):
    """Get a setting from settings.json file"""
    settings = read_json_file('settings.json', default={}) or {}
    return settings.get(key, default)

def get_settings():
    """Get all settings from settings.json file"""
    return read_json_file('settings.json', default={}) or {}

def is_feature_enabled(feature_key):
    """Check if a feature flag is enabled"""
    from app.models.feature_flag import FeatureFlag

    try:
        flag = FeatureFlag.query.filter_by(key=feature_key).first()
        return flag.enabled if flag else False
    except Exception:
        # Fallback to JSON file if database is not available
        settings = get_settings()
        return settings.get('feature_flags', {}).get(feature_key, False)