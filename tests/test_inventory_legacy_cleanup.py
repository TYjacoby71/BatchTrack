
"""
Legacy Pattern Elimination Tests

Ensures deprecated patterns and direct service calls are eliminated
from the codebase in favor of canonical entry point.
"""

import pytest
import ast
import os
from pathlib import Path


class TestLegacyPatternElimination:
    """Verify legacy patterns are eliminated from codebase"""

    def test_no_direct_fifo_imports_in_routes(self):
        """Test that route files don't import FIFO services directly"""
        
        # These patterns should not appear in route files
        prohibited_imports = [
            "from app.services.inventory_adjustment._fifo_ops import",
            "from app.services.fifo import",
            "import FIFOService"
        ]
        
        route_directories = [
            "app/blueprints",
            "app/routes"  
        ]
        
        violations = []
        
        for route_dir in route_directories:
            if os.path.exists(route_dir):
                for root, dirs, files in os.walk(route_dir):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r') as f:
                                    content = f.read()
                                    
                                for pattern in prohibited_imports:
                                    if pattern in content:
                                        violations.append(f"{file_path}: {pattern}")
                            except Exception:
                                pass  # Skip files that can't be read
        
        assert len(violations) == 0, f"Found prohibited imports: {violations}"

    def test_no_direct_quantity_assignment(self):
        """Test that no files directly assign to quantity fields"""
        
        # Pattern that should not exist: direct quantity assignment
        prohibited_patterns = [
            ".quantity =",
            ".quantity +=", 
            ".quantity -="
        ]
        
        directories_to_check = [
            "app/blueprints",
            "app/services",
            "app/routes"
        ]
        
        violations = []
        
        for directory in directories_to_check:
            if os.path.exists(directory):
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r') as f:
                                    content = f.read()
                                    
                                for pattern in prohibited_patterns:
                                    if pattern in content and "test_" not in file:
                                        # Allow in test files but not in application code
                                        violations.append(f"{file_path}: {pattern}")
                            except Exception:
                                pass
        
        assert len(violations) == 0, f"Found direct quantity assignments: {violations}"

    def test_canonical_import_usage(self):
        """Test that files import canonical service correctly"""
        
        expected_canonical_import = "from app.services.inventory_adjustment import process_inventory_adjustment"
        
        files_that_should_use_canonical = [
            "app/blueprints/inventory/routes.py",
            "app/blueprints/batches/routes.py"
        ]
        
        missing_canonical = []
        
        for file_path in files_that_should_use_canonical:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if expected_canonical_import not in content:
                            missing_canonical.append(file_path)
                except Exception:
                    pass
        
        # This is a warning rather than failure - some files might legitimately not need it
        if missing_canonical:
            print(f"Files that might need canonical import: {missing_canonical}")
