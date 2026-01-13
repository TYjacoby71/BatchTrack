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


_BINOMIAL_RE = re.compile(r"^([A-Za-z]{2,})\s+([A-Za-z]{2,})(?:\s+([A-Za-z]{2,}))?$")
_BINOMIAL_STOPWORDS = {
    # Not botanical identities
    "conditioning",
    "extract",
    "oil",
    "water",
    "juice",
    "puree",
    "purée",
    "pulp",
    "flavor",
    "fragrance",
    "essence",
    "specialty",
}


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
            source = _clean(getattr(row, "source", "")).lower()
            origin = _clean(getattr(row, "origin", "")).strip()
            physical_form = _clean(getattr(row, "derived_physical_form", "")).strip()

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
                # Form-only plant fats (e.g., Shea Butter) should bypass variation when variation is empty.
                # This prevents "missing variation" from being treated as a parsing gap.
                if origin == "Plant-Derived" and physical_form in {"Butter", "Wax", "Resin", "Gum", "Hydrosol", "Oil", "Powder", "Gel", "Paste"}:
                    new_bypass = 1
                    new_reason = "form_only"
                else:
                    raw_stripped = raw.strip(" ,")
                    low = raw_stripped.lower()
                    if _is_chemical_like(raw_stripped) or _is_chemical_like(inci):
                        new_bypass = 1
                        new_reason = "chemical_like"
                    else:
                        # TGSC often includes marketing/usage descriptors that are not meaningful
                        # ingredient variations (e.g., "... flavor", "... fragrance").
                        if raw_stripped and any(
                            low.endswith(f" {tok}") or low == tok
                            for tok in (
                                "flavor",
                                "fragrance",
                                "essence",
                                "specialty",
                                "enhancer",
                                "blockers",
                                "replacer",
                                "compound",
                            )
                        ):
                            new_bypass = 1
                            new_reason = "descriptor_only"
                        elif source == "tgsc" and raw_stripped and any(tok in low for tok in ("colouring matters", "coloring matters")):
                            new_bypass = 1
                            new_reason = "descriptor_only"
                        elif (
                            # TGSC sometimes includes long \"produced in / derived from\" enzyme/process descriptions
                            # without a clean ingredient identity; bypass rather than treating as missing variation.
                            source == "tgsc"
                            and not _clean(getattr(row, "cas_number", ""))
                            and raw_stripped
                            and any(tok in low for tok in (" produced in ", " derived from ", " expressing a gene ", " from "))
                        ):
                            new_bypass = 1
                            new_reason = "tgsc_process_descriptor"
                        elif (
                            # TGSC sometimes includes chemistry-like phrases without a CAS number.
                            # Treat these as identity-level (variation not meaningful) rather than "missing".
                            source == "tgsc"
                            and not _clean(getattr(row, "cas_number", ""))
                            and raw_stripped
                            and any(tok in low for tok in ("acetyl", "amido", "n-", "dl"))
                        ):
                            new_bypass = 1
                            new_reason = "tgsc_identity_phrase_no_cas"
                        elif (
                            # CosIng frequently contains chemistry identities that are all-caps phrases
                            # (e.g., "METHYL PYRROLIDONE") where a variation label is not meaningful.
                            source == "cosing"
                            and raw_stripped
                            and raw_stripped == raw_stripped.upper()
                            and " " in raw_stripped
                            and "/" not in raw_stripped
                            and not any(tok in low for tok in (" seed ", " kernel ", " nut ", " leaf ", " root ", " bark ", " flower ", " fruit ", " peel "))
                        ):
                            new_bypass = 1
                            new_reason = "cosing_caps_identity"
                        elif (
                            # TGSC: many named isolates end with a series suffix like "A," / "B," / "II,".
                            # These are identity-level names (not variations) and should bypass.
                            source == "tgsc"
                            and _clean(getattr(row, "cas_number", ""))  # strong identity hint
                            and raw_stripped
                            and re.search(r"\b([A-Z]|I|II|III|IV|V)\b\s*$", raw_stripped.rstrip(","))
                        ):
                            new_bypass = 1
                            new_reason = "tgsc_series_suffix"
                        elif (
                            # TGSC often contains multi-token chemical/trade names (with CAS) where a variation label
                            # is not meaningful (the name *is* the identity).
                            source == "tgsc"
                            and _clean(getattr(row, "cas_number", ""))
                            and raw_stripped
                            and not _BINOMIAL_RE.match(raw_stripped)  # avoid bypassing true botanicals
                        ):
                            new_bypass = 1
                            new_reason = "tgsc_identity_phrase"
                        elif raw_stripped and (" " not in raw_stripped) and ("/" not in raw_stripped) and len(raw_stripped) >= 3:
                            # Single token with no explicit form/variation (common for chemistry + some base materials).
                            new_bypass = 1
                            new_reason = "single_token"
                        elif raw_stripped and _BINOMIAL_RE.match(raw_stripped):
                            # Base botanical identity (e.g., "Panax ginseng") with no extra item modifiers.
                            m = _BINOMIAL_RE.match(raw_stripped)
                            genus = (m.group(1) or "").lower() if m else ""
                            species = (m.group(2) or "").lower() if m else ""
                            epithet = (m.group(3) or "").lower() if m else ""
                            if genus and species and species not in _BINOMIAL_STOPWORDS and genus not in _BINOMIAL_STOPWORDS:
                                # Avoid treating obviously non-botanical strings as botanicals (e.g. "Hair conditioning").
                                if not any(tok in (species, epithet) for tok in _BINOMIAL_STOPWORDS):
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

