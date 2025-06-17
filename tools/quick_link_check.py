
#!/usr/bin/env python3
import os
import re
from pathlib import Path

def quick_link_check():
    """Quick scan for obvious broken links"""
    issues = []
    
    print("🔍 Quick Link Check Starting...")
    
    # Check templates for common issues
    template_dirs = ['templates', 'app/blueprints/*/templates']
    
    for pattern in template_dirs:
        for template_dir in Path('.').glob(pattern):
            if template_dir.is_dir():
                for template_file in template_dir.rglob('*.html'):
                    with open(template_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        line_num = 0
                        
                        for line in content.split('\n'):
                            line_num += 1
                            
                            # Check for obvious broken static references
                            if 'url_for(' in line and 'static' in line:
                                # Extract filename
                                match = re.search(r"filename=['\"]([^'\"]+)['\"]", line)
                                if match:
                                    static_file = match.group(1)
                                    if not Path(f'static/{static_file}').exists():
                                        issues.append(f"❌ {template_file}:{line_num} - Missing static file: {static_file}")
                            
                            # Check for suspicious url_for calls
                            suspicious_patterns = [
                                'product_log.view_product',  # This looks broken based on your error
                                'dashboard.dashboard',
                                'inventory.list_inventory'
                            ]
                            
                            for pattern in suspicious_patterns:
                                if pattern in line:
                                    # Try to verify if the blueprint exists
                                    blueprint = pattern.split('.')[0]
                                    if not Path(f'app/blueprints/{blueprint}').exists():
                                        issues.append(f"⚠️  {template_file}:{line_num} - Suspicious blueprint: {pattern}")
    
    # Check for missing static files referenced in templates
    print("\n📊 RESULTS:")
    if not issues:
        print("✅ No obvious broken links found in quick scan!")
    else:
        print(f"Found {len(issues)} potential issues:")
        for issue in issues:
            print(issue)
    
    print("\n💡 For comprehensive checking, run: python tools/link_checker.py")

if __name__ == '__main__':
    quick_link_check()
