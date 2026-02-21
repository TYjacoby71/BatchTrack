#!/usr/bin/env python3
"""Repair legacy recipe test numbering by lineage scope.

Examples:
  Dry-run all orgs:
    python3 scripts/repair_recipe_test_sequences.py

  Apply to one organization:
    python3 scripts/repair_recipe_test_sequences.py --org-id 42 --apply

  Apply to one recipe group:
    python3 scripts/repair_recipe_test_sequences.py --group-id 123 --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.services.recipe_service import repair_test_sequences


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--org-id",
        type=int,
        default=None,
        help="Limit repair to one organization id.",
    )
    parser.add_argument(
        "--group-id",
        type=int,
        default=None,
        help="Limit repair to one recipe_group id.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=25,
        help="Max changed rows shown in preview output.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag, runs as dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    app = create_app()

    with app.app_context():
        result = repair_test_sequences(
            organization_id=args.org_id,
            recipe_group_id=args.group_id,
            apply_changes=bool(args.apply),
            preview_limit=args.preview_limit,
        )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Recipe test sequence repair summary")
    print(
        f"scanned={result['scanned']} buckets={result['buckets']} "
        f"sequence_updates={result['sequence_updates']} "
        f"renamed={result['renamed']} total_changes={result['total_changes']}"
    )
    if result["preview"]:
        print("preview:")
        print(json.dumps(result["preview"], indent=2, default=str))
    else:
        print("preview: []")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
