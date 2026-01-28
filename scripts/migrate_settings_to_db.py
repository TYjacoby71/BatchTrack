#!/usr/bin/env python3
"""Migrate settings.json payload into the database."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.utils.json_store import read_json_file
from app.utils.settings import get_settings, save_settings


def migrate_settings():
    app = create_app()
    with app.app_context():
        settings = read_json_file("settings.json", default=None)
        if not settings:
            print("ℹ️  No settings.json payload found to migrate.")
            return
        if isinstance(settings, dict):
            settings.pop("feature_flags", None)
        existing = get_settings()
        if existing:
            merged = dict(existing)
            for key, value in settings.items():
                if key not in merged:
                    merged[key] = value
            save_settings(merged)
            print("✅ Settings merged into app_setting (existing preserved)")
        else:
            save_settings(settings)
            print("✅ Settings migrated into app_setting")


if __name__ == "__main__":
    migrate_settings()
