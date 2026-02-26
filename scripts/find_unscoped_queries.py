#!/usr/bin/env python3
"""Find unscoped queries on scoped models in customer-facing blueprints."""

import re
import os

MODELS = [
    "Batch", "BatchIngredient", "BatchContainer", "BatchConsumable", "BatchTimer",
    "ExtraBatchIngredient", "ExtraBatchContainer", "ExtraBatchConsumable",
    "Recipe", "RecipeGroup", "RecipeIngredient", "RecipeConsumable", "RecipeLineage",
    "InventoryItem", "InventoryHistory", "InventoryLot",
    "Product", "ProductVariant", "ProductSKU",
    "Reservation", "Role", "Tag", "CustomUnitMapping", "ConversionLog",
    "UserPreferences", "IngredientCategory", "InventoryCategory", "UnifiedInventoryHistory",
]

BLUEPRINT_DIRS = [
    "app/blueprints/inventory",
    "app/blueprints/products",
    "app/blueprints/recipes",
    "app/blueprints/batches",
    "app/blueprints/timers",
    "app/blueprints/settings",
    "app/blueprints/organization",
    "app/blueprints/conversion",
    "app/blueprints/dashboard",
    "app/blueprints/expiration",
    "app/blueprints/bulk_stock",
    "app/blueprints/production_planning",
    "app/blueprints/recipe_library",
    "app/blueprints/core",
    "app/blueprints/billing",
    "app/blueprints/onboarding",
    "app/blueprints/api",
]

EXCLUDE_FILES = [
    "app/blueprints/api/public.py",
]

BASE = "/workspace"

SAFE_PATTERNS = [
    r'\.scoped\(',
    r'\.for_organization\(',
    r'\.for_current_user\(',
    r'\.filter_by\(\s*organization_id\s*=',
    r'\.filter\(\s*\w+\.organization_id\s*==',
]

def is_safe(line):
    for pat in SAFE_PATTERNS:
        if re.search(pat, line):
            return True
    return False

def collect_py_files():
    files = []
    for bp_dir in BLUEPRINT_DIRS:
        full_dir = os.path.join(BASE, bp_dir)
        if not os.path.isdir(full_dir):
            continue
        for root, dirs, filenames in os.walk(full_dir):
            for fn in filenames:
                if fn.endswith('.py'):
                    rel = os.path.relpath(os.path.join(root, fn), BASE)
                    if rel not in EXCLUDE_FILES:
                        files.append(os.path.join(root, fn))
    return sorted(files)

def build_patterns():
    patterns = []
    for model in MODELS:
        # ModelName.query.<method>
        patterns.append((
            re.compile(r'\b' + re.escape(model) + r'\.query\.\w+'),
            model,
            "ModelName.query.*"
        ))
        # db.session.query(ModelName
        patterns.append((
            re.compile(r'db\.session\.query\([^)]*\b' + re.escape(model) + r'\b'),
            model,
            "db.session.query(ModelName)"
        ))
    return patterns

def main():
    files = collect_py_files()
    patterns = build_patterns()
    
    findings = []
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
        except Exception:
            continue
        
        rel_path = os.path.relpath(filepath, BASE)
        
        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if is_safe(stripped):
                continue
            
            for regex, model, pattern_type in patterns:
                if regex.search(stripped):
                    # Extra check: for "Batch.query" make sure it's not "BatchIngredient.query" etc.
                    # The \b boundary should handle this, but let's be safe
                    # Also avoid false positives where model name is a substring
                    # e.g. "Batch" matching "BatchIngredient" - \b handles this
                    findings.append((rel_path, i, stripped.strip(), model))
                    break  # one finding per line
    
    # Sort by file, then line number
    findings.sort(key=lambda x: (x[0], x[1]))
    
    print(f"Total unscoped queries found: {len(findings)}\n")
    print("=" * 120)
    
    current_file = None
    for rel_path, lineno, code, model in findings:
        if rel_path != current_file:
            current_file = rel_path
            print(f"\n### {rel_path}")
            print("-" * 100)
        print(f"  Line {lineno:4d} | Model: {model:30s} | {code}")
    
    print("\n" + "=" * 120)
    print(f"\nSummary by model:")
    from collections import Counter
    model_counts = Counter(f[3] for f in findings)
    for model, count in sorted(model_counts.items(), key=lambda x: -x[1]):
        print(f"  {model:30s}: {count}")
    
    print(f"\nSummary by file:")
    file_counts = Counter(f[0] for f in findings)
    for fp, count in sorted(file_counts.items(), key=lambda x: -x[1]):
        print(f"  {fp:70s}: {count}")

if __name__ == '__main__':
    main()
