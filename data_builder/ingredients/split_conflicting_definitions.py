#!/usr/bin/env python3
"""Split definitions where clusters have conflicting common names."""
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split definitions with conflicting common names."
    )
    parser.add_argument(
        "--db-path",
        default="output/Final DB.db",
        help="Path to Final DB.db",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    return parser


def get_conflicting_definitions(conn: sqlite3.Connection) -> dict:
    """Find definitions where clusters have different common names."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT c.definition_id, c.cluster_id, c.raw_canonical_term, c.compiled_term, c.common_name
        FROM compiled_clusters c
        WHERE c.common_name IS NOT NULL 
          AND c.common_name != '' 
          AND c.common_name != 'N/A'
          AND c.definition_id IS NOT NULL
        ORDER BY c.definition_id
    ''')
    
    by_def = defaultdict(list)
    for def_id, cluster_id, raw_term, compiled_term, common_name in cur.fetchall():
        by_def[def_id].append({
            'cluster_id': cluster_id,
            'raw_term': raw_term,
            'compiled_term': compiled_term,
            'common_name': common_name
        })
    
    return by_def


def plan_splits(by_def: dict) -> list[dict]:
    """Determine which clusters need to be moved to new definitions."""
    splits = []
    
    for def_id, clusters in by_def.items():
        unique_names = set(c['common_name'] for c in clusters)
        if len(unique_names) <= 1:
            continue
        
        name_counts = defaultdict(int)
        for c in clusters:
            name_counts[c['common_name']] += 1
        majority_name = max(name_counts.keys(), key=lambda n: name_counts[n])
        
        for c in clusters:
            if c['common_name'] != majority_name:
                new_term = c['raw_term']
                if new_term == c['compiled_term']:
                    new_term = f"{c['raw_term']} ({c['common_name']})"
                
                splits.append({
                    'cluster_id': c['cluster_id'],
                    'old_def_id': def_id,
                    'old_term': c['compiled_term'],
                    'new_term': new_term,
                    'common_name': c['common_name']
                })
    
    return splits


def execute_splits(conn: sqlite3.Connection, splits: list[dict], dry_run: bool = False) -> dict:
    """Create new definitions and re-link clusters."""
    cur = conn.cursor()
    
    new_terms = set(s['new_term'] for s in splits)
    term_to_id = {}
    
    if not dry_run:
        for term in new_terms:
            cur.execute(
                "SELECT id FROM ingredient_definitions WHERE definition_term = ?",
                (term,)
            )
            row = cur.fetchone()
            if row:
                term_to_id[term] = row[0]
            else:
                cur.execute(
                    "INSERT INTO ingredient_definitions (definition_term, created_at, updated_at) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (term,)
                )
                term_to_id[term] = cur.lastrowid
        
        for s in splits:
            new_def_id = term_to_id[s['new_term']]
            cur.execute(
                "UPDATE compiled_clusters SET definition_id = ?, compiled_term = ? WHERE cluster_id = ?",
                (new_def_id, s['new_term'], s['cluster_id'])
            )
        
        conn.commit()
    
    return {
        'clusters_moved': len(splits),
        'new_definitions': len(new_terms),
        'term_to_id': term_to_id if not dry_run else {}
    }


def verify_no_conflicts(conn: sqlite3.Connection) -> int:
    """Count definitions that still have conflicting common names."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT d.id, COUNT(DISTINCT c.common_name) as name_count
        FROM ingredient_definitions d
        JOIN compiled_clusters c ON c.definition_id = d.id
        WHERE c.common_name IS NOT NULL 
          AND c.common_name != '' 
          AND c.common_name != 'N/A'
        GROUP BY d.id
        HAVING name_count > 1
    ''')
    
    return len(cur.fetchall())


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    
    print("Analyzing definitions for common name conflicts...")
    by_def = get_conflicting_definitions(conn)
    
    print("Planning splits...")
    splits = plan_splits(by_def)
    
    if not splits:
        print("No conflicts found. All definitions have consistent common names.")
        conn.close()
        return
    
    print(f"\nFound {len(splits)} clusters to split into {len(set(s['new_term'] for s in splits))} new definitions")
    
    if args.dry_run:
        print("\n[DRY RUN] Would create these new definitions:")
        for term in sorted(set(s['new_term'] for s in splits))[:20]:
            print(f"  - {term}")
        if len(set(s['new_term'] for s in splits)) > 20:
            print(f"  ... and {len(set(s['new_term'] for s in splits)) - 20} more")
    else:
        print("\nExecuting splits...")
        result = execute_splits(conn, splits)
        print(f"  Moved {result['clusters_moved']} clusters")
        print(f"  Created {result['new_definitions']} new definitions")
        
        remaining = verify_no_conflicts(conn)
        print(f"\nRemaining definitions with conflicts: {remaining}")
        
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ingredient_definitions")
        total_defs = cur.fetchone()[0]
        print(f"Total definitions now: {total_defs}")
    
    conn.close()


if __name__ == "__main__":
    main()
