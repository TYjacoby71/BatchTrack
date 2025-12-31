"""Mark SourceItem rows where variation is intentionally absent.

We currently derive `derived_variation` from the raw source name. However many items
do not meaningfully need a variation label (e.g., single-token chemicals like
"LIMONENE", numeric-leading INCI chemicals, etc.). This script classifies those as
`variation_bypass=1` with a reason so "missing variation" does not imply a parsing gap.
"""

from __future__ import annotations

import argparse
import logging
import re
from typing import Any

from . import database_manager

LOGGER = logging.getLogger(__name__)


def _clean(v: Any) -> str:
    return ("" if v is None else str(v)).strip()


def _is_chemical_like(name: str) -> bool:
    n = _clean(name)
    if not n:
        return False
    if n[0].isdigit():
        return True
    up = n.upper()
    if any(tok in up for tok in ("PEG-", "PPG-", "QUATERNIUM-", "POLY", "COPOLYMER", "CROSSPOLYMER")):
        return True
    if sum(ch.isdigit() for ch in n) >= 3:
        return True
    if any(sym in n for sym in ("-", "/", ",")) and any(ch.isdigit() for ch in n):
        return True
    return False


_BINOMIAL_RE = re.compile(r"^[A-Z][a-z]+ [a-z]{2,}(?: [a-z]{2,})?$")


def derive_variation_bypass(*, limit: int = 0) -> dict[str, int]:
    database_manager.ensure_tables_exist()

    scanned = 0
    updated = 0
    bypassed = 0

    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceItem)
        if limit and int(limit) > 0:
            q = q.limit(int(limit))

        for row in q.yield_per(2000):
            scanned += 1

            # If we already derived a variation, it's not a bypass.
            has_var = bool(_clean(getattr(row, "derived_variation", "")))
            is_comp = bool(getattr(row, "is_composite", False))
            raw = _clean(getattr(row, "raw_name", ""))
            inci = _clean(getattr(row, "inci_name", ""))

            new_bypass = 0
            new_reason: str | None = None

            if has_var:
                new_bypass = 0
                new_reason = None
            elif is_comp:
                # Composite/mixture: treat as "needs review", not bypass.
                new_bypass = 0
                new_reason = None
            else:
                if _is_chemical_like(raw) or _is_chemical_like(inci):
                    new_bypass = 1
                    new_reason = "chemical_like"
                elif raw:
                    low = raw.lower().strip(" ,")
                    # TGSC often includes marketing/usage descriptors that are not meaningful
                    # ingredient variations (e.g., "... flavor", "... fragrance").
                    if any(low.endswith(f" {tok}") or low == tok for tok in ("flavor", "fragrance", "essence", "specialty")):
                        new_bypass = 1
                        new_reason = "descriptor_only"
                elif raw and (" " not in raw) and ("/" not in raw) and len(raw) >= 4:
                    # Single token with no explicit form/variation.
                    new_bypass = 1
                    new_reason = "single_token"
                elif raw and _BINOMIAL_RE.match(raw):
                    # Base botanical identity (e.g. "Panax ginseng") with no extra item modifiers.
                    new_bypass = 1
                    new_reason = "botanical_base"

            old_bypass = int(getattr(row, "variation_bypass", 0) or 0)
            old_reason = getattr(row, "variation_bypass_reason", None)

            if old_bypass != new_bypass or (old_reason or None) != (new_reason or None):
                row.variation_bypass = int(new_bypass)
                row.variation_bypass_reason = new_reason
                updated += 1
            if new_bypass:
                bypassed += 1

    return {"scanned": scanned, "updated": updated, "bypassed": bypassed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive variation_bypass flags for source_items")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows (debug)")
    args = parser.parse_args()

    stats = derive_variation_bypass(limit=int(args.limit or 0))
    print(stats)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

