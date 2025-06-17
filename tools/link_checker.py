
import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse
import ast

class LinkChecker:
    def __init__(self, app_root='.'):
        self.app_root = Path(app_root)
        self.issues = []
        self.routes = set()
        self.static_files = set()
        self.templates = set()
        
    def scan_routes(self):
        """Extract all Flask routes from blueprint files"""
        print("Scanning routes...")
        route_files = [
            'app/auth/routes.py',
            'app/blueprints/*/routes.py',
            'app/blueprints/*/api.py',
            'app/blueprints/*/*.py'
        ]
        
        for pattern in route_files:
            for file_path in self.app_root.glob(pattern):
                self._extract_routes_from_file(file_path)
    
    def _extract_routes_from_file(self, file_path):
        """Extract route patterns from Python files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find @app.route or @bp.route decorators
            route_patterns = re.findall(r'@\w+\.route\([\'"]([^\'"]+)[\'"]', content)
            for pattern in route_patterns:
                # Convert Flask route patterns to regex-like for checking
                clean_pattern = pattern.replace('<', '').replace('>', '').replace('int:', '').replace('string:', '')
                self.routes.add(clean_pattern)
                
        except Exception as e:
            self.issues.append({
                'file': str(file_path),
                'type': 'route_scan_error',
                'issue': f"Error scanning routes: {str(e)}"
            })
    
    def scan_static_files(self):
        """Find all static files"""
        print("Scanning static files...")
        static_dirs = ['static', 'app/static']
        
        for static_dir in static_dirs:
            static_path = self.app_root / static_dir
            if static_path.exists():
                for file_path in static_path.rglob('*'):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(static_path)
                        self.static_files.add(str(rel_path))
    
    def scan_templates(self):
        """Find all template files"""
        print("Scanning templates...")
        template_dirs = ['templates', 'app/templates', 'app/blueprints/*/templates']
        
        for pattern in template_dirs:
            for template_dir in self.app_root.glob(pattern):
                if template_dir.is_dir():
                    for file_path in template_dir.rglob('*.html'):
                        rel_path = file_path.relative_to(self.app_root / 'templates' if (self.app_root / 'templates').exists() else template_dir)
                        self.templates.add(str(rel_path))
    
    def check_template_links(self):
        """Check all links in template files"""
        print("Checking template links...")
        template_dirs = ['templates', 'app/templates', 'app/blueprints/*/templates']
        
        for pattern in template_dirs:
            for template_dir in self.app_root.glob(pattern):
                if template_dir.is_dir():
                    for file_path in template_dir.rglob('*.html'):
                        self._check_template_file(file_path)
    
    def _check_template_file(self, file_path):
        """Check individual template file for broken links"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check url_for() calls
            url_for_patterns = re.findall(r"url_for\(['\"]([^'\"]+)['\"](?:,\s*([^)]+))?\)", content)
            for endpoint, params in url_for_patterns:
                self._validate_url_for(file_path, endpoint, params)
            
            # Check static file references
            static_patterns = re.findall(r"url_for\(['\"]static['\"],\s*filename=['\"]([^'\"]+)['\"]", content)
            for static_file in static_patterns:
                self._validate_static_file(file_path, static_file)
            
            # Check href and src attributes for relative URLs
            href_patterns = re.findall(r'(?:href|src)=[\'"]([^\'\"]+)[\'"]', content)
            for url in href_patterns:
                if url.startswith('/') and not url.startswith('//'):
                    self._validate_relative_url(file_path, url)
                    
        except Exception as e:
            self.issues.append({
                'file': str(file_path),
                'type': 'template_scan_error',
                'issue': f"Error scanning template: {str(e)}"
            })
    
    def _validate_url_for(self, file_path, endpoint, params):
        """Validate url_for endpoint exists"""
        # Check if it's a blueprint endpoint
        if '.' in endpoint:
            blueprint, route = endpoint.split('.', 1)
            # This is a simplified check - you might want to enhance this
            expected_file = f"app/blueprints/{blueprint}/routes.py"
            if not (self.app_root / expected_file).exists():
                self.issues.append({
                    'file': str(file_path),
                    'type': 'missing_blueprint',
                    'issue': f"Blueprint '{blueprint}' not found for endpoint '{endpoint}'"
                })
        
        # Check for common endpoint patterns
        common_endpoints = [
            'index', 'dashboard.dashboard', 'inventory.list_inventory',
            'recipes.list_recipes', 'batches.list_batches', 'products.product_list',
            'settings.index', 'logout', 'login'
        ]
        
        if endpoint not in common_endpoints and '.' not in endpoint:
            self.issues.append({
                'file': str(file_path),
                'type': 'suspicious_endpoint',
                'issue': f"Endpoint '{endpoint}' might not exist"
            })
    
    def _validate_static_file(self, file_path, static_file):
        """Validate static file exists"""
        if static_file not in self.static_files:
            # Check if file actually exists
            static_path = self.app_root / 'static' / static_file
            if not static_path.exists():
                self.issues.append({
                    'file': str(file_path),
                    'type': 'missing_static_file',
                    'issue': f"Static file '{static_file}' not found"
                })
    
    def _validate_relative_url(self, file_path, url):
        """Validate relative URLs"""
        # Basic validation for common patterns
        if url.startswith('/static/'):
            static_file = url[8:]  # Remove '/static/'
            self._validate_static_file(file_path, static_file)
        elif url.startswith('/'):
            # Check if it matches any known route patterns
            found_match = False
            for route in self.routes:
                if url.startswith(route.replace('<', '').replace('>', '')):
                    found_match = True
                    break
            
            if not found_match and len(url) > 1:  # Ignore root '/'
                self.issues.append({
                    'file': str(file_path),
                    'type': 'unmatched_route',
                    'issue': f"URL '{url}' doesn't match any known routes"
                })
    
    def check_javascript_links(self):
        """Check links in JavaScript files"""
        print("Checking JavaScript files...")
        js_files = list(self.app_root.glob('static/js/**/*.js'))
        
        for js_file in js_files:
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for fetch() calls and AJAX URLs
                url_patterns = re.findall(r'(?:fetch|ajax|url:)\s*[\'"]([^\'\"]+)[\'"]', content, re.IGNORECASE)
                for url in url_patterns:
                    if url.startswith('/') and not url.startswith('//'):
                        self._validate_relative_url(js_file, url)
                        
            except Exception as e:
                self.issues.append({
                    'file': str(js_file),
                    'type': 'js_scan_error',
                    'issue': f"Error scanning JavaScript: {str(e)}"
                })
    
    def generate_report(self):
        """Generate comprehensive report"""
        print(f"\n{'='*60}")
        print("BROKEN LINK CHECKER REPORT")
        print(f"{'='*60}")
        
        if not self.issues:
            print("✅ No broken links found!")
            return
        
        # Group issues by type
        by_type = {}
        for issue in self.issues:
            issue_type = issue['type']
            if issue_type not in by_type:
                by_type[issue_type] = []
            by_type[issue_type].append(issue)
        
        # Print summary
        print(f"Total issues found: {len(self.issues)}\n")
        
        for issue_type, issues in by_type.items():
            print(f"\n{issue_type.upper().replace('_', ' ')} ({len(issues)} issues):")
            print("-" * 40)
            
            for issue in issues:
                print(f"📁 {issue['file']}")
                print(f"   ❌ {issue['issue']}")
                print()
    
    def save_report(self, filename='link_check_report.json'):
        """Save detailed report to JSON"""
        report = {
            'timestamp': str(Path().resolve()),
            'total_issues': len(self.issues),
            'routes_found': len(self.routes),
            'static_files_found': len(self.static_files),
            'templates_found': len(self.templates),
            'issues': self.issues
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print(f"📋 Detailed report saved to: {filename}")
    
    def run_full_check(self):
        """Run complete link checking process"""
        print("🔍 Starting comprehensive link check...")
        
        self.scan_routes()
        self.scan_static_files()
        self.scan_templates()
        self.check_template_links()
        self.check_javascript_links()
        
        self.generate_report()
        self.save_report()

def main():
    checker = LinkChecker()
    checker.run_full_check()

if __name__ == '__main__':
    main()
