
#!/usr/bin/env python3

import os
import re
from flask import Flask
from app import create_app
from app.models import User, Organization

def find_subscription_tier_conditionals():
    """Find all template files with subscription tier conditionals"""
    print("=== SCANNING FOR SUBSCRIPTION TIER CONDITIONALS ===\n")
    
    template_dirs = [
        'app/templates',
        'app/blueprints'
    ]
    
    conditional_patterns = [
        r'subscription_tier\s*[!=><]+',
        r'current_user\.organization\.subscription',
        r'organization\.subscription',
        r'tier\s*[!=><]+\s*[\'"]exempt[\'"]',
        r'exempt.*tier',
        r'{% if.*tier.*%}',
        r'{% if.*subscription.*%}'
    ]
    
    found_files = []
    
    for template_dir in template_dirs:
        if os.path.exists(template_dir):
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith(('.html', '.py')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                            for pattern in conditional_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    found_files.append((file_path, pattern, matches))
                                    print(f"🔍 {file_path}")
                                    print(f"   Pattern: {pattern}")
                                    print(f"   Matches: {matches}")
                                    
                                    # Show context around matches
                                    lines = content.split('\n')
                                    for i, line in enumerate(lines):
                                        if re.search(pattern, line, re.IGNORECASE):
                                            start = max(0, i-2)
                                            end = min(len(lines), i+3)
                                            print(f"   Context (lines {start+1}-{end}):")
                                            for j in range(start, end):
                                                marker = ">>> " if j == i else "    "
                                                print(f"   {marker}{j+1}: {lines[j]}")
                                    print()
                        except Exception as e:
                            pass
    
    return found_files

def check_org8_specifically():
    """Check Organization 8 details"""
    print("=== ORGANIZATION 8 DETAILS ===")
    
    app = create_app()
    with app.app_context():
        org8 = Organization.query.get(8)
        if org8:
            print(f"Name: {org8.name}")
            print(f"Subscription tier: {org8.subscription_tier}")
            print(f"Active: {org8.is_active}")
            
            # Check if there's a subscription record
            if hasattr(org8, 'subscription') and org8.subscription:
                print(f"Has subscription record: Yes")
                print(f"Subscription status: {org8.subscription.status}")
            else:
                print(f"Has subscription record: No")
                
            print()

def check_javascript_includes():
    """Check for JavaScript file inclusions in templates"""
    print("=== JAVASCRIPT INCLUSION PATTERNS ===\n")
    
    js_patterns = [
        r'<script.*src.*ingredient.*\.js',
        r'<script.*src.*recipe.*\.js', 
        r'<script.*src.*modal.*\.js',
        r'{% if.*%}.*<script',
        r'<script.*addIngredient',
        r'function addIngredient'
    ]
    
    template_files = []
    for root, dirs, files in os.walk('app/templates'):
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))
    
    for template_file in template_files:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in js_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    print(f"📄 {template_file}")
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            print(f"   Line {i+1}: {line.strip()}")
                    print()
        except Exception as e:
            pass

if __name__ == "__main__":
    print("🐛 DEBUGGING TEMPLATE CONDITIONALS FOR ORG 8\n")
    
    # Check org 8 details
    check_org8_specifically()
    
    # Find subscription tier conditionals
    conditionals = find_subscription_tier_conditionals()
    
    # Check JavaScript includes
    check_javascript_includes()
    
    print(f"\n📊 SUMMARY:")
    print(f"Found {len(conditionals)} files with subscription tier conditionals")
    print(f"This is likely causing the JavaScript loading issues for Org 8")
