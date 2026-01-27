
#!/usr/bin/env python3
"""Migrate feature flags into the database without resetting values."""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.seeders.feature_flag_seeder import seed_feature_flags
from app.utils.json_store import read_json_file

def migrate_feature_flags():
    """Import existing flag values from settings.json, then seed missing flags."""
    app = create_app()

    with app.app_context():
        from app.extensions import db
        from app.models.feature_flag import FeatureFlag

        settings = read_json_file("settings.json", default=None) or {}
        legacy_flags = settings.get("feature_flags") if isinstance(settings, dict) else {}
        if isinstance(legacy_flags, dict):
            for key, enabled in legacy_flags.items():
                existing = FeatureFlag.query.filter_by(key=key).first()
                if existing:
                    continue
                db.session.add(
                    FeatureFlag(
                        key=key,
                        enabled=bool(enabled),
                        description=f"Migrated from settings.json",
                    )
                )
            db.session.commit()

        # Ensure catalog flags exist (does not override enabled state)
        seed_feature_flags()

if __name__ == '__main__':
    migrate_feature_flags()
