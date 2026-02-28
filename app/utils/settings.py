from __future__ import annotations
import logging

import copy
from typing import Any, Dict

logger = logging.getLogger(__name__)


DEFAULT_SETTINGS_KEY = "settings"


class SettingsService:
    """DB-backed settings manager for operational toggles."""

    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from the database into memory."""
        self._settings = get_settings()
        return self._settings

    def save_settings(self) -> bool:
        """Persist the in-memory settings to the database."""
        return save_settings(self._settings)

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


def _read_settings() -> Dict[str, Any]:
    return get_settings()


def _resolve_nested(
    settings: Dict[str, Any], dotted_key: str, default: Any = None
) -> Any:
    if not dotted_key:
        return settings
    parts = dotted_key.split(".")
    value: Any = settings
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def get_setting(key: str, default: Any = None) -> Any:
    """
    Retrieve a setting from the database store.

    Supports dotted paths (e.g., ``alerts.expiration_warning_days``) for nested structures.
    """
    settings = _read_settings()
    return _resolve_nested(settings, key, default)


def get_settings() -> Dict[str, Any]:
    """Return the full settings payload."""
    return copy.deepcopy(get_app_setting(DEFAULT_SETTINGS_KEY, default={}) or {})


def save_settings(settings: Dict[str, Any]) -> bool:
    """Persist the full settings payload."""
    return set_app_setting(DEFAULT_SETTINGS_KEY, settings)


def update_settings_payload(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge updates into the persisted settings payload."""
    settings = get_settings()
    settings.update(updates)
    save_settings(settings)
    return settings


def update_settings_value(section: str, key: str, value: Any) -> Dict[str, Any]:
    """Update a single setting within a named section."""
    settings = get_settings()
    section_payload = settings.get(section)
    if not isinstance(section_payload, dict):
        section_payload = {}
    section_payload[key] = value
    settings[section] = section_payload
    save_settings(settings)
    return settings


def get_app_setting(key: str, default: Any = None) -> Any:
    """Fetch a raw setting by key."""
    from app.models.app_setting import AppSetting

    try:
        entry = AppSetting.query.filter_by(key=key).first()
        if entry is not None and entry.value is not None:
            return copy.deepcopy(entry.value)
    except Exception:
        logger.warning("Suppressed exception fallback at app/utils/settings.py:121", exc_info=True)
        pass
    return copy.deepcopy(default)


def set_app_setting(key: str, value: Any, *, description: str | None = None) -> bool:
    """Persist a raw setting by key."""
    from app.extensions import db
    from app.models.app_setting import AppSetting

    try:
        entry = AppSetting.query.filter_by(key=key).first()
        if entry:
            entry.value = value
            if description is not None:
                entry.description = description
        else:
            entry = AppSetting(key=key, value=value, description=description)
            db.session.add(entry)
        db.session.commit()
        return True
    except Exception:
        logger.warning("Suppressed exception fallback at app/utils/settings.py:142", exc_info=True)
        db.session.rollback()
        return False


def is_feature_enabled(feature_key: str) -> bool:
    """Determine whether a feature flag is enabled (database only)."""
    from app.models.feature_flag import FeatureFlag

    try:
        flag = FeatureFlag.query.filter_by(key=feature_key).first()
        if flag is not None:
            return bool(flag.enabled)
    except Exception:
        logger.warning("Suppressed exception fallback at app/utils/settings.py:155", exc_info=True)
        pass
    try:
        from app.services.developer.dashboard_service import FEATURE_FLAG_SECTIONS

        for section in FEATURE_FLAG_SECTIONS:
            for flag in section.get("flags", []):
                if flag.get("key") == feature_key:
                    return bool(
                        flag.get(
                            "default_enabled",
                            flag.get("always_on", False),
                        )
                    )
    except Exception:
        logger.warning("Suppressed exception fallback at app/utils/settings.py:169", exc_info=True)
        pass
    return False
