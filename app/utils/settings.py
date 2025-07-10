import json
import os
from typing import Any, Dict, Optional

class SettingsService:
    """Service for managing application settings"""

    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    self._settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._settings = {}
        return self._settings

    def save_settings(self) -> bool:
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
            return True
        except IOError:
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
    try:
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                return settings.get(key, default)
        return default
    except:
        return default