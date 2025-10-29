"""
Simple Error Message Compliance Test

A simpler version that checks basic compliance without heavy AST parsing.
Run with: pytest tests/test_error_compliance_simple.py -v
"""

import re
from pathlib import Path
import pytest


def get_route_files():
    """Get all route files in the application"""
    workspace_root = Path(__file__).parent.parent
    route_files = []
    
    # Get all route files
    routes_dir = workspace_root / 'app' / 'routes'
    if routes_dir.exists():
        route_files.extend(routes_dir.glob('*.py'))
    
    blueprints_dir = workspace_root / 'app' / 'blueprints'
    if blueprints_dir.exists():
        for blueprint in blueprints_dir.iterdir():
            if blueprint.is_dir():
                route_files.extend(blueprint.glob('*routes*.py'))
                route_files.extend(blueprint.glob('routes.py'))
    
    return [f for f in route_files if f.name != '__init__.py']


def scan_file_for_patterns(filepath):
    """Scan a file for error message anti-patterns"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return []
    
    violations = []
    relative_path = str(filepath.relative_to(Path(__file__).parent.parent))
    
    # Skip test files
    if 'test_' in relative_path:
        return []
    
    # Pattern 1: Check for flash without category
    # Match: flash('message') but not flash('message', 'category')
    for line_num, line in enumerate(content.split('\n'), 1):
        if 'flash(' in line and '"' in line or "'" in line:
            # Simple check: if flash( has a string but no comma after the closing quote
            if re.search(r"flash\(['\"].*?['\"]\)(?!\s*,)", line):
                violations.append({
                    'file': relative_path,
                    'line': line_num,
                    'type': 'NO_CATEGORY',
                    'snippet': line.strip()[:70]
                })
    
    # Pattern 2: Check for hardcoded error strings in flash
    # Look for: flash('Error', 'error') or flash("Failed to", 'error')
    error_keywords = ['error', 'failed', 'cannot', 'unable', 'invalid', 'missing']
    for line_num, line in enumerate(content.split('\n'), 1):
        if 'flash(' in line and "'error'" in line.lower():
            for keyword in error_keywords:
                if keyword in line.lower() and 'EM.' not in line and 'ErrorMessages' not in line:
                    # Likely a hardcoded error
                    violations.append({
                        'file': relative_path,
                        'line': line_num,
                        'type': 'HARDCODED_ERROR',
                        'snippet': line.strip()[:70]
                    })
                    break
    
    return violations


class TestErrorMessageCompliance:
    """Tests for error message compliance"""
    
    def test_error_messages_file_exists(self):
        """Test that the centralized error_messages.py exists"""
        workspace_root = Path(__file__).parent.parent
        error_messages_path = workspace_root / 'app' / 'utils' / 'error_messages.py'
        
        assert error_messages_path.exists(), \
            "app/utils/error_messages.py not found. Please create the centralized error messages file."
    
    def test_error_messages_has_classes(self):
        """Test that error_messages.py has required classes"""
        workspace_root = Path(__file__).parent.parent
        error_messages_path = workspace_root / 'app' / 'utils' / 'error_messages.py'
        
        with open(error_messages_path, 'r') as f:
            content = f.read()
        
        assert 'class ErrorMessages:' in content, "ErrorMessages class not found"
        assert 'class SuccessMessages:' in content, "SuccessMessages class not found"
        
        # Check for some basic messages
        assert '_NOT_FOUND' in content, "No NOT_FOUND error messages defined"
        assert '_FAILED' in content, "No FAILED error messages defined"
    
    def test_layout_template_has_categories(self):
        """Test that layout.html uses flash message categories"""
        workspace_root = Path(__file__).parent.parent
        layout_path = workspace_root / 'app' / 'templates' / 'layout.html'
        
        assert layout_path.exists(), "app/templates/layout.html not found"
        
        with open(layout_path, 'r') as f:
            content = f.read()
        
        assert 'with_categories' in content, \
            "layout.html should use get_flashed_messages(with_categories=true)"
    
    def test_documentation_exists(self):
        """Test that error protocol documentation exists"""
        workspace_root = Path(__file__).parent.parent
        docs_path = workspace_root / 'docs'
        
        required_docs = [
            'ERROR_MESSAGE_PROTOCOL.md',
            'ROUTE_DEVELOPMENT_GUIDE.md',
        ]
        
        for doc in required_docs:
            doc_path = docs_path / doc
            assert doc_path.exists(), \
                f"Missing documentation: docs/{doc}. Please create developer documentation."
    
    def test_sample_routes_for_compliance(self):
        """Sample check: Scan a few route files for obvious violations"""
        route_files = get_route_files()
        
        if not route_files:
            pytest.skip("No route files found to test")
        
        # Check up to 10 route files
        files_to_check = route_files[:10]
        all_violations = []
        
        for filepath in files_to_check:
            violations = scan_file_for_patterns(filepath)
            all_violations.extend(violations)
        
        # This is a warning test - it doesn't fail, just reports
        if all_violations:
            message = "\n\n" + "="*80 + "\n"
            message += "⚠️  POTENTIAL ERROR MESSAGE ISSUES FOUND (Sample)\n"
            message += "="*80 + "\n\n"
            message += "This is not a failure, but consider migrating these to centralized messages.\n\n"
            
            # Group by type
            no_category = [v for v in all_violations if v['type'] == 'NO_CATEGORY']
            hardcoded = [v for v in all_violations if v['type'] == 'HARDCODED_ERROR']
            
            if no_category:
                message += f"\n📋 Flash without category: {len(no_category)} found\n"
                for v in no_category[:3]:
                    message += f"   {v['file']}:{v['line']}\n"
                    message += f"   {v['snippet']}\n"
            
            if hardcoded:
                message += f"\n📝 Hardcoded errors: {len(hardcoded)} found\n"
                for v in hardcoded[:3]:
                    message += f"   {v['file']}:{v['line']}\n"
                    message += f"   {v['snippet']}\n"
            
            message += "\n" + "="*80 + "\n"
            message += "See docs/ERROR_MESSAGE_PROTOCOL.md for migration guide.\n"
            message += "="*80 + "\n"
            
            print(message)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
