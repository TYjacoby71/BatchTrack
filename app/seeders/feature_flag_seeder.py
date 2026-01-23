#!/usr/bin/env python3
"""Seed feature flags from the catalog."""

from __future__ import annotations

from typing import Dict, Iterable

from app.extensions import db
from app.models.feature_flag import FeatureFlag
from app.services.developer.dashboard_service import FEATURE_FLAG_SECTIONS


def _iter_catalog_flags() -> Iterable[Dict[str, object]]:
    for section in FEATURE_FLAG_SECTIONS:
        for flag in section.get("flags", []):
            key = flag.get("key")
            if not key:
                continue
            default_enabled = bool(
                flag.get("default_enabled", flag.get("always_on", False))
            )
            description = flag.get("description") or flag.get("label") or key
            yield {
                "key": key,
                "default_enabled": default_enabled,
                "description": description,
            }


def seed_feature_flags() -> None:
    """Ensure feature flags exist in the database."""
    try:
        created = 0
        updated = 0
        for entry in _iter_catalog_flags():
            existing = FeatureFlag.query.filter_by(key=entry["key"]).first()
            if existing:
                existing.description = entry["description"]
                updated += 1
            else:
                db.session.add(
                    FeatureFlag(
                        key=entry["key"],
                        enabled=bool(entry["default_enabled"]),
                        description=entry["description"],
                    )
                )
                created += 1
        db.session.commit()
        print(
            f"✅ Feature flags seeded: {created} created, {updated} updated"
        )
    except Exception as exc:
        db.session.rollback()
        print(f"❌ Error seeding feature flags: {exc}")
        raise
