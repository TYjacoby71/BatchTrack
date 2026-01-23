
#!/usr/bin/env python3
"""Seed feature flags into the database."""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.seeders.feature_flag_seeder import seed_feature_flags

def migrate_feature_flags():
    """Seed feature flags from the catalog into the database."""
    app = create_app()
    
    with app.app_context():
        seed_feature_flags()

if __name__ == '__main__':
    migrate_feature_flags()
