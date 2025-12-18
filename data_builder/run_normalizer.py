
#!/usr/bin/env python3
"""
Standalone entry point for the ingredient normalizer.
"""

import sys
import os
from pathlib import Path

# Add the data_builder directory to Python path
DATA_BUILDER_ROOT = Path(__file__).parent
sys.path.insert(0, str(DATA_BUILDER_ROOT))

# Set up environment for data builder
os.environ.setdefault('COMPILER_DB_PATH', str(DATA_BUILDER_ROOT / 'ingredients' / 'compiler_state.db'))

# Import and run the normalizer
from ingredients.normalize_sources import main

if __name__ == "__main__":
    main()
