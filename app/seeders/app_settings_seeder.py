#!/usr/bin/env python3
"""Seed app settings defaults."""

from __future__ import annotations
import logging

import copy

from app.extensions import db
from app.models.app_setting import AppSetting
from app.utils.settings import DEFAULT_SETTINGS_KEY
from app.utils.settings_defaults import DEFAULT_APP_SETTINGS, merge_settings_defaults

logger = logging.getLogger(__name__)



def seed_app_settings() -> None:
    """Ensure default app settings are present."""
    try:
        existing = AppSetting.query.filter_by(key=DEFAULT_SETTINGS_KEY).first()
        if existing:
            current = existing.value or {}
            if isinstance(current, dict):
                current = {k: v for k, v in current.items() if k != "feature_flags"}
            else:
                current = {}
            merged = merge_settings_defaults(current)
            existing.value = merged
        else:
            payload = copy.deepcopy(DEFAULT_APP_SETTINGS)
            existing = AppSetting(key=DEFAULT_SETTINGS_KEY, value=payload)
            db.session.add(existing)
        db.session.commit()
        print("✅ App settings seeded")
    except Exception as exc:
        logger.warning("Suppressed exception fallback at app/seeders/app_settings_seeder.py:32", exc_info=True)
        db.session.rollback()
        print(f"❌ Error seeding app settings: {exc}")
        raise
