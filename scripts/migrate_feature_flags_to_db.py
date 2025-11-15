
#!/usr/bin/env python3
"""
Migration script to move feature flags from settings.json to database
"""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.extensions import db
from app.models.feature_flag import FeatureFlag
from app.utils.settings import get_settings

def migrate_feature_flags():
    """Migrate feature flags from JSON to database"""
    app = create_app()
    
    with app.app_context():
        try:
            # Get feature flags from JSON file
            settings = get_settings()
            json_flags = settings.get('feature_flags', {})
            
            if not json_flags:
                print("No feature flags found in settings.json")
                return
            
            migrated_count = 0
            updated_count = 0
            
            for flag_key, enabled in json_flags.items():
                # Check if flag already exists in database
                existing_flag = FeatureFlag.query.filter_by(key=flag_key).first()
                
                if existing_flag:
                    # Update existing flag
                    existing_flag.enabled = bool(enabled)
                    updated_count += 1
                    print(f"Updated existing flag: {flag_key} = {enabled}")
                else:
                    # Create new flag
                    new_flag = FeatureFlag(
                        key=flag_key,
                        enabled=bool(enabled),
                        description=f"Migrated from settings.json"
                    )
                    db.session.add(new_flag)
                    migrated_count += 1
                    print(f"Migrated new flag: {flag_key} = {enabled}")
            
            # Commit changes
            db.session.commit()
            
            print(f"\n✅ Migration completed:")
            print(f"   - {migrated_count} new flags created")
            print(f"   - {updated_count} existing flags updated")
            print(f"   - Total flags processed: {len(json_flags)}")
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_feature_flags()
