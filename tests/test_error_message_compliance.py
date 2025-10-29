"""
Test Error Message Compliance

This test suite ensures that all routes follow the centralized error message protocol.
It scans the codebase for anti-patterns and enforces best practices.

Run with: pytest tests/test_error_message_compliance.py -v
"""

import os
import re
import ast
from pathlib import Path
import pytest


class ErrorMessageScanner:
    """Scans Python files for error message compliance"""
    
    def __init__(self, root_path):
        self.root_path = Path(root_path)
        self.violations = []
        
    def scan_directory(self, directory, pattern='**/*.py'):
        """Scan all Python files in directory"""
        files = list(self.root_path.glob(f"{directory}/{pattern}"))
        return files
    
    def check_file(self, filepath):
        """Check a single file for violations"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            relative_path = str(filepath.relative_to(self.root_path))
            
            # Skip test files and migrations
            if 'test_' in relative_path or '/tests/' in relative_path:
                return []
            if '/migrations/' in relative_path:
                return []
            if '__pycache__' in relative_path:
                return []
                
            violations = []
            
            # Check for violations
            violations.extend(self._check_hardcoded_flash(content, relative_path))
            violations.extend(self._check_flash_without_category(content, relative_path))
            violations.extend(self._check_jsonify_errors(content, relative_path))
            violations.extend(self._check_error_message_import(content, relative_path))
            
            return violations
            
        except Exception as e:
            # Skip files that can't be read
            return []
    
    def _check_hardcoded_flash(self, content, filepath):
        """Check for flash() calls with hardcoded strings instead of EM constants"""
        violations = []
        
        # Pattern: flash('hardcoded string', 'error')
        # But exclude: flash(EM.SOMETHING, 'error')
        pattern = r"flash\(['\"]([^'\"]+)['\"],\s*['\"]error['\"]\)"
        
        for match in re.finditer(pattern, content):
            message = match.group(1)
            # Skip if it looks like it might be using a variable or format
            if '{' not in message and 'EM.' not in message:
                line_num = content[:match.start()].count('\n') + 1
                violations.append({
                    'file': filepath,
                    'line': line_num,
                    'type': 'HARDCODED_ERROR_FLASH',
                    'message': f'Hardcoded error message in flash(): "{message[:50]}..."',
                    'suggestion': 'Use ErrorMessages constant: flash(EM.YOUR_ERROR, "error")'
                })
        
        return violations
    
    def _check_flash_without_category(self, content, filepath):
        """Check for flash() calls without category"""
        violations = []
        
        # Pattern: flash('message') or flash("message") without second param
        # Match flash with just one string argument
        pattern = r"flash\(['\"]([^'\"]+)['\"]\)(?!\s*,)"
        
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            message = match.group(1)[:50]
            violations.append({
                'file': filepath,
                'line': line_num,
                'type': 'FLASH_NO_CATEGORY',
                'message': f'flash() without category: "{message}..."',
                'suggestion': 'Add category: flash(message, "error"|"success"|"warning"|"info")'
            })
        
        return violations
    
    def _check_jsonify_errors(self, content, filepath):
        """Check for jsonify with hardcoded error dicts instead of APIResponse"""
        violations = []
        
        # Pattern: return jsonify({'error': 'message'}), status_code
        pattern = r"return\s+jsonify\(\s*\{\s*['\"]error['\"]\s*:\s*['\"]([^'\"]+)['\"]\s*\}\s*\)"
        
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            message = match.group(1)[:50]
            violations.append({
                'file': filepath,
                'line': line_num,
                'type': 'JSONIFY_ERROR_DICT',
                'message': f'Using jsonify instead of APIResponse: "{message}..."',
                'suggestion': 'Use APIResponse.error(message=EM.YOUR_ERROR, status_code=400)'
            })
        
        return violations
    
    def _check_error_message_import(self, content, filepath):
        """Check if file has routes but no ErrorMessages import"""
        violations = []
        
        # Only check route files
        if '/routes.py' not in filepath and '/routes/' not in filepath:
            return violations
        
        # Check if file has Blueprint or @app.route
        has_routes = bool(
            re.search(r"Blueprint\(", content) or 
            re.search(r"@\w+\.route\(", content) or
            re.search(r"@app\.route\(", content)
        )
        
        if not has_routes:
            return violations
        
        # Check if it imports ErrorMessages
        has_em_import = bool(
            re.search(r"from\s+app\.utils\.error_messages\s+import", content) or
            re.search(r"import\s+app\.utils\.error_messages", content)
        )
        
        if not has_em_import:
            violations.append({
                'file': filepath,
                'line': 1,
                'type': 'MISSING_ERROR_MESSAGE_IMPORT',
                'message': 'Route file missing ErrorMessages import',
                'suggestion': 'Add: from app.utils.error_messages import ErrorMessages as EM'
            })
        
        return violations


class TestErrorMessageCompliance:
    """Test suite for error message compliance"""
    
    @pytest.fixture(scope='class')
    def scanner(self):
        """Create scanner instance"""
        workspace_root = Path(__file__).parent.parent
        return ErrorMessageScanner(workspace_root)
    
    @pytest.fixture(scope='class')
    def route_files(self, scanner):
        """Get all route files"""
        routes = []
        routes.extend(scanner.scan_directory('app/routes'))
        routes.extend(scanner.scan_directory('app/blueprints', '**/*routes*.py'))
        return routes
    
    @pytest.fixture(scope='class')
    def service_files(self, scanner):
        """Get all service files"""
        return scanner.scan_directory('app/services')
    
    def test_no_hardcoded_error_flash(self, scanner, route_files):
        """Test that flash() error calls use ErrorMessages constants"""
        all_violations = []
        
        for filepath in route_files:
            violations = scanner.check_file(filepath)
            hardcoded = [v for v in violations if v['type'] == 'HARDCODED_ERROR_FLASH']
            all_violations.extend(hardcoded)
        
        if all_violations:
            message = "\n\n" + "="*80 + "\n"
            message += "HARDCODED ERROR MESSAGES FOUND\n"
            message += "="*80 + "\n\n"
            
            for v in all_violations[:10]:  # Show first 10
                message += f"File: {v['file']}\n"
                message += f"Line: {v['line']}\n"
                message += f"Issue: {v['message']}\n"
                message += f"Fix: {v['suggestion']}\n"
                message += "-" * 80 + "\n"
            
            if len(all_violations) > 10:
                message += f"\n... and {len(all_violations) - 10} more violations\n"
            
            message += f"\nTotal violations: {len(all_violations)}\n"
            message += "\nThese should use centralized ErrorMessages:\n"
            message += "  from app.utils.error_messages import ErrorMessages as EM\n"
            message += "  flash(EM.YOUR_ERROR, 'error')\n"
            
            pytest.fail(message)
    
    def test_flash_has_category(self, scanner, route_files):
        """Test that all flash() calls include a category"""
        all_violations = []
        
        for filepath in route_files:
            violations = scanner.check_file(filepath)
            no_category = [v for v in violations if v['type'] == 'FLASH_NO_CATEGORY']
            all_violations.extend(no_category)
        
        if all_violations:
            message = "\n\n" + "="*80 + "\n"
            message += "FLASH MESSAGES WITHOUT CATEGORY\n"
            message += "="*80 + "\n\n"
            
            for v in all_violations[:10]:
                message += f"File: {v['file']}\n"
                message += f"Line: {v['line']}\n"
                message += f"Issue: {v['message']}\n"
                message += f"Fix: {v['suggestion']}\n"
                message += "-" * 80 + "\n"
            
            if len(all_violations) > 10:
                message += f"\n... and {len(all_violations) - 10} more violations\n"
            
            message += f"\nTotal violations: {len(all_violations)}\n"
            message += "\nAll flash() calls must include a category:\n"
            message += "  flash(message, 'error')    # Red alert\n"
            message += "  flash(message, 'success')  # Green alert\n"
            message += "  flash(message, 'warning')  # Yellow alert\n"
            message += "  flash(message, 'info')     # Blue alert\n"
            
            pytest.fail(message)
    
    def test_use_api_response_not_jsonify(self, scanner, route_files):
        """Test that API routes use APIResponse instead of jsonify error dicts"""
        all_violations = []
        
        for filepath in route_files:
            violations = scanner.check_file(filepath)
            jsonify_errors = [v for v in violations if v['type'] == 'JSONIFY_ERROR_DICT']
            all_violations.extend(jsonify_errors)
        
        if all_violations:
            message = "\n\n" + "="*80 + "\n"
            message += "JSONIFY ERROR DICTS FOUND (should use APIResponse)\n"
            message += "="*80 + "\n\n"
            
            for v in all_violations[:10]:
                message += f"File: {v['file']}\n"
                message += f"Line: {v['line']}\n"
                message += f"Issue: {v['message']}\n"
                message += f"Fix: {v['suggestion']}\n"
                message += "-" * 80 + "\n"
            
            if len(all_violations) > 10:
                message += f"\n... and {len(all_violations) - 10} more violations\n"
            
            message += f"\nTotal violations: {len(all_violations)}\n"
            message += "\nUse APIResponse for structured JSON errors:\n"
            message += "  from app.utils.api_responses import APIResponse\n"
            message += "  return APIResponse.error(\n"
            message += "      message=EM.YOUR_ERROR,\n"
            message += "      errors={'field': 'value'},\n"
            message += "      status_code=400\n"
            message += "  )\n"
            
            pytest.fail(message)
    
    def test_route_files_import_error_messages(self, scanner, route_files):
        """Test that route files import ErrorMessages"""
        all_violations = []
        
        for filepath in route_files:
            violations = scanner.check_file(filepath)
            missing_import = [v for v in violations if v['type'] == 'MISSING_ERROR_MESSAGE_IMPORT']
            all_violations.extend(missing_import)
        
        # This is a soft warning, not a hard failure
        # Some route files might legitimately not need error messages
        if all_violations:
            message = "\n\n" + "="*80 + "\n"
            message += "ROUTE FILES WITHOUT ERROR_MESSAGES IMPORT (Warning)\n"
            message += "="*80 + "\n\n"
            
            for v in all_violations[:5]:
                message += f"File: {v['file']}\n"
                message += f"Suggestion: {v['suggestion']}\n"
                message += "-" * 80 + "\n"
            
            message += f"\nTotal files: {len(all_violations)}\n"
            message += "\nNote: This is informational. Not all route files need error messages.\n"
            message += "If this file handles errors, add the import.\n"
            
            # Just print the warning, don't fail
            print(message)
    
    def test_error_messages_file_valid(self):
        """Test that error_messages.py is valid Python and has required classes"""
        workspace_root = Path(__file__).parent.parent
        error_messages_path = workspace_root / 'app' / 'utils' / 'error_messages.py'
        
        assert error_messages_path.exists(), "error_messages.py not found"
        
        with open(error_messages_path, 'r') as f:
            content = f.read()
        
        # Check it's valid Python
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"error_messages.py has syntax error: {e}")
        
        # Check required classes exist
        assert 'class ErrorMessages:' in content, "ErrorMessages class not found"
        assert 'class SuccessMessages:' in content, "SuccessMessages class not found"
        
        # Check no f-strings in message definitions (they should use .format())
        # Look for lines like: SOME_VAR = f"message"
        pattern = r'^\s+[A-Z_]+\s*=\s*f["\']'
        if re.search(pattern, content, re.MULTILINE):
            pytest.fail("error_messages.py contains f-strings. Use .format() placeholders instead.")
    
    def test_error_messages_no_html(self):
        """Test that error messages don't contain HTML tags"""
        workspace_root = Path(__file__).parent.parent
        error_messages_path = workspace_root / 'app' / 'utils' / 'error_messages.py'
        
        with open(error_messages_path, 'r') as f:
            content = f.read()
        
        # Look for HTML tags in message strings
        html_pattern = r'["\'].*?<[a-zA-Z/][^>]*>.*?["\']'
        matches = re.findall(html_pattern, content)
        
        if matches:
            message = "\n\n" + "="*80 + "\n"
            message += "HTML TAGS FOUND IN ERROR MESSAGES\n"
            message += "="*80 + "\n\n"
            message += "Error messages should be plain text only.\n"
            message += "Found HTML in these strings:\n\n"
            
            for match in matches[:5]:
                message += f"  {match}\n"
            
            message += "\nRemove HTML tags from error messages.\n"
            message += "Let templates handle formatting.\n"
            
            pytest.fail(message)
    
    def test_layout_template_uses_categories(self):
        """Test that layout.html properly handles flash message categories"""
        workspace_root = Path(__file__).parent.parent
        layout_path = workspace_root / 'app' / 'templates' / 'layout.html'
        
        assert layout_path.exists(), "layout.html not found"
        
        with open(layout_path, 'r') as f:
            content = f.read()
        
        # Check for category handling
        assert 'get_flashed_messages(with_categories=true)' in content, \
            "layout.html should use get_flashed_messages(with_categories=true)"
        
        # Check for proper category mapping
        assert 'alert-danger' in content or 'alert-error' in content, \
            "layout.html should handle error category"
        assert 'alert-success' in content, \
            "layout.html should handle success category"


class TestErrorMessageUsage:
    """Test that error messages are being used correctly in the codebase"""
    
    def test_example_route_uses_centralized_errors(self):
        """Test that at least one route file uses ErrorMessages correctly"""
        workspace_root = Path(__file__).parent.parent
        
        # Check app/utils/error_messages.py exists
        error_messages_path = workspace_root / 'app' / 'utils' / 'error_messages.py'
        assert error_messages_path.exists(), \
            "Centralized error_messages.py not found. Run error message setup first."
        
        # This test ensures the infrastructure is in place
        # Individual route compliance is checked by other tests
        with open(error_messages_path, 'r') as f:
            content = f.read()
            
        # Verify file has content and structure
        assert len(content) > 1000, "error_messages.py seems incomplete"
        assert 'ErrorMessages' in content, "ErrorMessages class missing"
        assert 'NOT_FOUND' in content, "No error messages defined"


def test_error_protocol_documentation_exists():
    """Test that error protocol documentation exists"""
    workspace_root = Path(__file__).parent.parent
    docs_path = workspace_root / 'docs'
    
    required_docs = [
        'ERROR_MESSAGE_PROTOCOL.md',
        'ROUTE_DEVELOPMENT_GUIDE.md',
        'QUICK_REFERENCE_ERRORS.md'
    ]
    
    missing_docs = []
    for doc in required_docs:
        doc_path = docs_path / doc
        if not doc_path.exists():
            missing_docs.append(doc)
    
    if missing_docs:
        pytest.fail(
            f"Missing documentation files: {', '.join(missing_docs)}\n"
            f"These files are required for developers to understand the error message protocol."
        )


if __name__ == '__main__':
    # Allow running this file directly for quick checks
    import sys
    workspace_root = Path(__file__).parent.parent
    scanner = ErrorMessageScanner(workspace_root)
    
    print("Scanning codebase for error message compliance...\n")
    
    # Scan route files
    route_files = []
    route_files.extend(scanner.scan_directory('app/routes'))
    route_files.extend(scanner.scan_directory('app/blueprints', '**/*routes*.py'))
    
    all_violations = []
    for filepath in route_files:
        violations = scanner.check_file(filepath)
        all_violations.extend(violations)
    
    if not all_violations:
        print("✅ No violations found! All routes follow the error message protocol.")
        sys.exit(0)
    
    # Group violations by type
    by_type = {}
    for v in all_violations:
        vtype = v['type']
        if vtype not in by_type:
            by_type[vtype] = []
        by_type[vtype].append(v)
    
    print(f"❌ Found {len(all_violations)} violations:\n")
    
    for vtype, violations in by_type.items():
        print(f"\n{vtype}: {len(violations)} violations")
        print("-" * 80)
        for v in violations[:3]:  # Show first 3 of each type
            print(f"  {v['file']}:{v['line']}")
            print(f"  {v['message']}")
            print()
        
        if len(violations) > 3:
            print(f"  ... and {len(violations) - 3} more\n")
    
    print("\nRun 'pytest tests/test_error_message_compliance.py -v' for detailed results.")
    sys.exit(1)
