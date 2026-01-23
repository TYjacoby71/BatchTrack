#!/usr/bin/env python3
"""Upgrade config data to DB-backed settings and flags (non-destructive)."""

from __future__ import annotations

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models.feature_flag import FeatureFlag
from app.seeders.app_settings_seeder import seed_app_settings
from app.seeders.feature_flag_seeder import seed_feature_flags
from app.utils.json_store import read_json_file
from app.utils.settings import get_settings, save_settings


def upgrade_config():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "app_setting" not in tables:
            print("❌ app_setting table missing. Run `flask db upgrade` first.")
            return

        # Migrate settings.json payload into app_setting without overwriting existing.
        settings_payload = read_json_file("settings.json", default=None) or {}
        if isinstance(settings_payload, dict):
            settings_payload.pop("feature_flags", None)
        if settings_payload:
            existing = get_settings()
            if existing:
                merged = dict(existing)
                for key, value in settings_payload.items():
                    if key not in merged:
                        merged[key] = value
                save_settings(merged)
                print("✅ Settings merged into app_setting (existing preserved)")
            else:
                save_settings(settings_payload)
                print("✅ Settings migrated into app_setting")
        else:
            print("ℹ️  No settings.json payload found to migrate.")

        # Migrate feature flags from settings.json without overwriting DB values.
        legacy_flags = {}
        if isinstance(settings_payload, dict):
            legacy_flags = (read_json_file("settings.json", default=None) or {}).get(
                "feature_flags", {}
            )
        if isinstance(legacy_flags, dict) and legacy_flags:
            for key, enabled in legacy_flags.items():
                if FeatureFlag.query.filter_by(key=key).first():
                    continue
                db.session.add(
                    FeatureFlag(
                        key=key,
                        enabled=bool(enabled),
                        description="Migrated from settings.json",
                    )
                )
            db.session.commit()
            print("✅ Feature flags migrated from settings.json")

        # Ensure any new flags/settings exist (does not override enabled values).
        seed_feature_flags()
        seed_app_settings()
        print("✅ Config upgrade complete")


if __name__ == "__main__":
    upgrade_config()
