#!/usr/bin/env python3
"""Audit and split refined ingredient definitions by common-name conflicts.

This script treats refined ingredient definitions as their own objects when the
ingredient_definitions table exists, otherwise falls back to compiled_term. It
detects definitions where clusters disagree on common_name, and (optionally)
reassigns those clusters to new definition terms using botanical_name or
original terms.

Default behavior:
- Only Plant-Derived clusters are eligible for reassignment.
- Clusters with "tallow" in the term/common name are skipped.
- No changes are written unless --apply is passed.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import database_manager


@dataclass(frozen=True)
class ClusterRow:
    cluster_id: str
    compiled_term: str
    raw_canonical_term: str
    common_name: str
    botanical_name: str
    inci_name: str
    cas_number: str
    origin: str
    ingredient_category: str
    payload_json: str
    definition_id: int | None
    definition_term: str


_PLACEHOLDER_COMMON = {"", "n/a", "not found", "unknown"}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def normalize_common_name(value: str | None) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    lowered = raw.lower().strip()
    if lowered in _PLACEHOLDER_COMMON:
        return ""
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\s\-]", "", lowered)
    return lowered.strip()


def definition_key(row: ClusterRow) -> str:
    return _clean(row.definition_term) or _clean(row.compiled_term) or _clean(row.raw_canonical_term) or row.cluster_id


def is_plant_derived(row: ClusterRow) -> bool:
    return _clean(row.origin) == "Plant-Derived"


def is_tallow(row: ClusterRow) -> bool:
    haystack = " ".join([row.compiled_term, row.raw_canonical_term, row.common_name]).lower()
    return "tallow" in haystack


def pick_target_term(row: ClusterRow) -> str:
    """Choose the refined definition term for a cluster when splitting conflicts."""
    botanical = _clean(row.botanical_name)
    if botanical:
        return botanical
    raw = _clean(row.raw_canonical_term)
    if raw:
        return raw
    inci = _clean(row.inci_name)
    if inci:
        return inci
    cas = _clean(row.cas_number)
    if cas:
        return cas
    return _clean(row.compiled_term) or row.cluster_id


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
    return cur.fetchone() is not None


def load_clusters(conn: sqlite3.Connection) -> list[ClusterRow]:
    cur = conn.cursor()
    has_definitions = _table_exists(conn, "ingredient_definitions")
    if has_definitions:
        cur.execute(
            """
            SELECT c.cluster_id,
                   c.compiled_term,
                   c.raw_canonical_term,
                   c.common_name,
                   c.botanical_name,
                   c.inci_name,
                   c.cas_number,
                   c.origin,
                   c.ingredient_category,
                   c.payload_json,
                   d.id,
                   d.definition_term
            FROM compiled_clusters c
            LEFT JOIN ingredient_definitions d ON c.definition_id = d.id
            WHERE EXISTS (
                SELECT 1 FROM compiled_cluster_items i WHERE i.cluster_id = c.cluster_id
            )
            """
        )
    else:
        cur.execute(
            """
            SELECT c.cluster_id,
                   c.compiled_term,
                   c.raw_canonical_term,
                   c.common_name,
                   c.botanical_name,
                   c.inci_name,
                   c.cas_number,
                   c.origin,
                   c.ingredient_category,
                   c.payload_json,
                   NULL as definition_id,
                   NULL as definition_term
            FROM compiled_clusters c
            WHERE EXISTS (
                SELECT 1 FROM compiled_cluster_items i WHERE i.cluster_id = c.cluster_id
            )
            """
        )
    rows = []
    for r in cur.fetchall():
        rows.append(
            ClusterRow(
                cluster_id=_clean(r[0]),
                compiled_term=_clean(r[1]),
                raw_canonical_term=_clean(r[2]),
                common_name=_clean(r[3]),
                botanical_name=_clean(r[4]),
                inci_name=_clean(r[5]),
                cas_number=_clean(r[6]),
                origin=_clean(r[7]),
                ingredient_category=_clean(r[8]),
                payload_json=r[9] or "",
                definition_id=(int(r[10]) if r[10] is not None else None),
                definition_term=_clean(r[11]),
            )
        )
    return rows


def group_by_definition(rows: Iterable[ClusterRow]) -> dict[str, list[ClusterRow]]:
    grouped: dict[str, list[ClusterRow]] = {}
    for row in rows:
        key = definition_key(row)
        grouped.setdefault(key, []).append(row)
    return grouped


def find_conflicts(grouped: dict[str, list[ClusterRow]]) -> dict[str, list[ClusterRow]]:
    conflicts: dict[str, list[ClusterRow]] = {}
    for key, rows in grouped.items():
        common_names = {normalize_common_name(r.common_name) for r in rows}
        common_names.discard("")
        if len(common_names) > 1:
            conflicts[key] = rows
    return conflicts


def print_definition_summary(key: str, rows: list[ClusterRow]) -> None:
    common_names = sorted({normalize_common_name(r.common_name) or "-" for r in rows})
    print(f"\nDefinition: {key}")
    print(f"  Clusters: {len(rows)}")
    print(f"  Common names: {', '.join(common_names)}")
    for row in rows:
        print(
            f"    - {row.cluster_id} | common_name={row.common_name or '-'}"
            f" | botanical={row.botanical_name or '-'} | origin={row.origin or '-'}"
        )


def update_payload_term(payload_json: str, new_term: str) -> str:
    if not payload_json:
        return payload_json
    try:
        payload = json.loads(payload_json)
    except Exception:
        return payload_json
    if isinstance(payload, dict) and isinstance(payload.get("stage1"), dict):
        payload["stage1"]["term"] = new_term
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _ensure_definition(conn: sqlite3.Connection, term: str) -> int | None:
    if not _table_exists(conn, "ingredient_definitions"):
        return None
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT OR IGNORE INTO ingredient_definitions (definition_term, created_at, updated_at)
        VALUES (?, ?, ?)
        """,
        (term, now, now),
    )
    cur.execute("SELECT id FROM ingredient_definitions WHERE definition_term = ?", (term,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def apply_updates(
    conn: sqlite3.Connection,
    updates: list[tuple[str, str, str]],
) -> int:
    """Apply updates: (cluster_id, new_term, new_payload_json)."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    for cluster_id, new_term, new_payload in updates:
        definition_id = _ensure_definition(conn, new_term)
        if definition_id is None:
            cur.execute(
                """
                UPDATE compiled_clusters
                SET compiled_term = ?, payload_json = ?, updated_at = ?
                WHERE cluster_id = ?
                """,
                (new_term, new_payload, now, cluster_id),
            )
        else:
            cur.execute(
                """
                UPDATE compiled_clusters
                SET compiled_term = ?, definition_id = ?, payload_json = ?, updated_at = ?
                WHERE cluster_id = ?
                """,
                (new_term, definition_id, new_payload, now, cluster_id),
            )
    conn.commit()
    return len(updates)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and split refined ingredient definitions.")
    parser.add_argument(
        "--db-path",
        default=str(database_manager.DB_PATH),
        help="Path to Final DB.db (defaults to COMPILER_DB_PATH or output/Final DB.db).",
    )
    parser.add_argument(
        "--definition",
        default="",
        help="Inspect a specific definition term (case-sensitive).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max conflict definitions to print.",
    )
    parser.add_argument(
        "--include-non-plant",
        action="store_true",
        help="Include non-plant-derived clusters when applying splits.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply reassignment updates to compiled_clusters.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    rows = load_clusters(conn)
    grouped = group_by_definition(rows)
    conflicts = find_conflicts(grouped)

    print(f"Total definitions: {len(grouped)}")
    print(f"Definitions with common-name conflicts: {len(conflicts)}")
    print(f"Total clusters: {len(rows)}")

    if args.definition:
        rows_for_definition = grouped.get(args.definition)
        if not rows_for_definition:
            print(f"\nDefinition not found: {args.definition}")
        else:
            print_definition_summary(args.definition, rows_for_definition)

    if conflicts:
        print("\nSample conflicts:")
        for idx, (key, rows_for_def) in enumerate(conflicts.items()):
            if idx >= args.limit:
                print(f"... ({len(conflicts) - args.limit} more)")
                break
            print_definition_summary(key, rows_for_def)

    updates: list[tuple[str, str, str]] = []
    for key, rows_for_def in conflicts.items():
        for row in rows_for_def:
            if not args.include_non_plant and not is_plant_derived(row):
                continue
            if is_tallow(row):
                continue
            new_term = pick_target_term(row)
            if not new_term:
                continue
            if _clean(row.compiled_term) == new_term:
                continue
            new_payload = update_payload_term(row.payload_json, new_term)
            updates.append((row.cluster_id, new_term, new_payload))

    print(f"\nClusters eligible for reassignment: {len(updates)}")
    if updates:
        sample = updates[: min(10, len(updates))]
        print("Sample updates:")
        for cluster_id, new_term, _ in sample:
            print(f"  - {cluster_id} -> {new_term}")

    if args.apply:
        count = apply_updates(conn, updates)
        print(f"\nApplied updates: {count}")
    else:
        print("\nDry run only. Use --apply to write changes.")
    conn.close()


if __name__ == "__main__":
    main()
