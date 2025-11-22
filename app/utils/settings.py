from __future__ import annotations

from typing import Any, Dict

from .json_store import read_json_file, write_json_file

DEFAULT_SETTINGS_FILE = "settings.json"


class SettingsService:
    """Simple JSON-backed settings manager for operational toggles."""

    def __init__(self, settings_file: str = DEFAULT_SETTINGS_FILE):
        self.settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from disk into memory."""
        self._settings = read_json_file(self.settings_file, default={}) or {}
        return self._settings

    def save_settings(self) -> bool:
        """Persist the in-memory settings to disk."""
        try:
            write_json_file(self.settings_file, self._settings)
            return True
        except OSError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key* if present, else *default*."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Set a single setting and persist the change."""
        self._settings[key] = value
        return self.save_settings()

    def get_all(self) -> Dict[str, Any]:
        """Return a copy of all settings."""
        return self._settings.copy()

    def update_multiple(self, settings: Dict[str, Any]) -> bool:
        """Atomically update a batch of settings."""
        self._settings.update(settings)
        return self.save_settings()

    def delete(self, key: str) -> bool:
        """Remove a setting if present."""
        if key in self._settings:
            del self._settings[key]
            return self.save_settings()
        return False


# Alias retained for historical imports
SettingsManager = SettingsService


def _read_settings(settings_file: str = DEFAULT_SETTINGS_FILE) -> Dict[str, Any]:
    return read_json_file(settings_file, default={}) or {}


def _resolve_nested(settings: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    if not dotted_key:
        return settings
    parts = dotted_key.split(".")
    value: Any = settings
    for part in parts:
        if not isinstance(value, Dict) or part not in value:
            return default
        value = value[part]
    return value


def get_setting(key: str, default: Any = None, *, settings_file: str = DEFAULT_SETTINGS_FILE) -> Any:
    """
    Retrieve a setting from the JSON store.

    Supports dotted paths (e.g., ``alerts.expiration_warning_days``) for nested structures.
    """
    settings = _read_settings(settings_file)
    return _resolve_nested(settings, key, default)


def get_settings(*, settings_file: str = DEFAULT_SETTINGS_FILE) -> Dict[str, Any]:
    """Return the full settings payload."""
    return _read_settings(settings_file)


def is_feature_enabled(feature_key: str, *, settings_file: str = DEFAULT_SETTINGS_FILE) -> bool:
    """Determine whether a feature flag is enabled."""
    from app.models.feature_flag import FeatureFlag

    try:
        flag = FeatureFlag.query.filter_by(key=feature_key).first()
        if flag is not None:
            return bool(flag.enabled)
    except Exception:
        pass

    # Fallback to the JSON file when the database is unavailable (e.g., during CLI scripts).
    settings = get_settings(settings_file=settings_file)
    feature_flags = settings.get("feature_flags", {})
    return bool(feature_flags.get(feature_key, False))