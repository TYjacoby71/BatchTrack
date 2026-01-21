"""
Batch Refinement Script

This script applies post-compilation refinement rules to the compiled database.
Unlike the flag detection (which only marks items), this script will actually
change the data when run.

Usage:
    python batch_refinement.py --dry-run     # Preview changes without applying
    python batch_refinement.py --apply       # Actually modify the database
    python batch_refinement.py --flag=NAME   # Only process items with specific flag
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data_builder.ingredients.database_manager import (
    REFINEMENT_RULES,
    configure_db_path,
    get_session,
    CompiledClusterItemRecord,
    CompiledClusterRecord,
    get_refinement_flag_summary,
    get_items_by_refinement_flag,
)


def apply_kernel_to_seed(item: CompiledClusterItemRecord, dry_run: bool = True) -> dict:
    """Convert 'Kernel Oil' variation to 'Seed Oil'.
    
    Kernel is the inner part of the seed - botanically they're the same product.
    This normalizes terminology.
    """
    changes = {
        "item_id": item.id,
        "derived_term": item.derived_term,
        "old_variation": item.derived_variation,
        "new_variation": "Seed Oil",
        "applied": False,
    }
    
    if not dry_run:
        item.derived_variation = "Seed Oil"
        item.updated_at = datetime.utcnow()
        changes["applied"] = True
    
    return changes


def apply_fixed_to_carrier(item: CompiledClusterItemRecord, dry_run: bool = True) -> dict:
    """Handle 'Fixed Oil' items.
    
    Fixed Oil is the INCI/technical term for non-volatile oils.
    - Keep variation as 'Fixed Oil' (it's technically correct)
    - Ensure master_category is set to 'Carrier Oils' in item_json
    """
    changes = {
        "item_id": item.id,
        "derived_term": item.derived_term,
        "old_variation": item.derived_variation,
        "action": "Ensure master_category = Carrier Oils",
        "applied": False,
    }
    
    if not dry_run:
        try:
            item_data = json.loads(item.item_json) if item.item_json else {}
        except:
            item_data = {}
        
        if item_data.get("master_category") != "Carrier Oils":
            item_data["master_category"] = "Carrier Oils"
            item.item_json = json.dumps(item_data)
            item.updated_at = datetime.utcnow()
            changes["applied"] = True
            changes["master_category_set"] = True
        else:
            changes["already_set"] = True
    
    return changes


def apply_generic_extract(item: CompiledClusterItemRecord, dry_run: bool = True) -> dict:
    """Review generic 'Extract' items.
    
    This is a review flag - we don't automatically change these.
    The plant part should ideally come from source data or AI inference.
    """
    return {
        "item_id": item.id,
        "derived_term": item.derived_term,
        "variation": item.derived_variation,
        "action": "Manual review needed - plant part not specified",
        "applied": False,  # Never auto-apply
    }


REFINEMENT_HANDLERS = {
    "kernel_to_seed": apply_kernel_to_seed,
    "fixed_to_carrier": apply_fixed_to_carrier,
    "generic_extract": apply_generic_extract,
}


def run_batch_refinement(
    db_path: str = "output/Final DB.db",
    dry_run: bool = True,
    target_flag: str | None = None,
) -> dict:
    """Run batch refinement on all flagged items.
    
    Args:
        db_path: Path to the database
        dry_run: If True, only preview changes without applying
        target_flag: If specified, only process items with this flag
    
    Returns:
        Summary of changes made/previewed
    """
    configure_db_path(db_path)
    
    summary = get_refinement_flag_summary()
    print(f"Refinement flag summary: {summary}")
    
    results = {
        "dry_run": dry_run,
        "flags_processed": {},
        "total_items": 0,
        "changes_applied": 0,
    }
    
    flags_to_process = [target_flag] if target_flag else list(REFINEMENT_HANDLERS.keys())
    
    with get_session() as session:
        for flag in flags_to_process:
            if flag not in REFINEMENT_HANDLERS:
                print(f"No handler for flag: {flag}")
                continue
            
            handler = REFINEMENT_HANDLERS[flag]
            items = get_items_by_refinement_flag(flag)
            
            print(f"\nProcessing flag '{flag}': {len(items)} items")
            results["flags_processed"][flag] = []
            
            for item_info in items:
                item = session.query(CompiledClusterItemRecord).get(item_info["id"])
                if not item:
                    continue
                
                change = handler(item, dry_run=dry_run)
                results["flags_processed"][flag].append(change)
                results["total_items"] += 1
                
                if change.get("applied"):
                    results["changes_applied"] += 1
        
        if not dry_run:
            session.commit()
            print(f"\nCommitted {results['changes_applied']} changes to database")
        else:
            print(f"\n[DRY RUN] Would apply {len([c for f in results['flags_processed'].values() for c in f])} changes")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Batch refinement script for compiled ingredient data")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview changes without applying")
    parser.add_argument("--apply", action="store_true", help="Actually modify the database")
    parser.add_argument("--flag", type=str, help="Only process items with this specific flag")
    parser.add_argument("--db", type=str, default="output/Final DB.db", help="Database path")
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    print("=" * 60)
    print("BATCH REFINEMENT SCRIPT")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY CHANGES'}")
    print(f"Database: {args.db}")
    if args.flag:
        print(f"Target flag: {args.flag}")
    print("=" * 60)
    
    results = run_batch_refinement(
        db_path=args.db,
        dry_run=dry_run,
        target_flag=args.flag,
    )
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print(f"Total items processed: {results['total_items']}")
    print(f"Changes applied: {results['changes_applied']}")
    
    for flag, changes in results["flags_processed"].items():
        print(f"\n{flag}:")
        for c in changes[:5]:  # Show first 5
            print(f"  - {c.get('derived_term', 'N/A')}: {c.get('action', c.get('new_variation', 'reviewed'))}")
        if len(changes) > 5:
            print(f"  ... and {len(changes) - 5} more")


if __name__ == "__main__":
    main()
