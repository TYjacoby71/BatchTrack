"""Deterministically normalize source CSVs into base ingredient terms.

Outputs:
- data_builder/ingredients/output/normalized_terms.csv
- Upserts normalized term records into compiler_state.db (normalized_terms table)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:  # pragma: no cover - allow running as a script
    from . import database_manager
except ImportError:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from data_builder.ingredients import database_manager  # type: ignore

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_SOURCES_DIR = BASE_DIR / "data_sources"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = OUTPUT_DIR / "normalized_terms.csv"


_DROP_TOKENS_RE = re.compile(
    r"\b("
    r"essential\s+oil|co2\s+extract|supercritical\s+extract|absolute|hydrosol|distillate|"
    r"tincture|glycerite|alcohol\s+extract|vinegar\s+extract|extract|"
    r"\d+(\.\d+)?\s*%|solution|"
    r"refined|unrefined|deodorized|filtered|unfiltered|unsweetened|sweetened|"
    r")\b",
    flags=re.IGNORECASE,
)

_PUNCT_RE = re.compile(r"[^\w\s\-\&/]", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_base_name(raw: str) -> str:
    """Convert a messy source name into a canonical base term (best-effort)."""
    if not raw:
        return ""
    value = str(raw).strip().strip('"').strip()
    value = value.rstrip(",").strip()
    if not value:
        return ""

    # Remove stray HTML-ish/JS noise.
    value = value.replace("\u00a0", " ")
    value = _PUNCT_RE.sub(" ", value)
    value = _SPACE_RE.sub(" ", value).strip()

    # Remove known non-base tokens.
    value = _DROP_TOKENS_RE.sub("", value)
    value = _SPACE_RE.sub(" ", value).strip(" -/").strip()

    # Collapse obvious INCI blends and polymers to avoid nonsense bases.
    if "/" in value and len(value.split("/")) >= 3:
        return ""
    if any(token in value.upper() for token in ("COPOLYMER", "ACRYLATES", "POLYMER")):
        return ""

    # Title-case while preserving acronyms.
    parts = []
    for part in value.split(" "):
        if part.isupper() and len(part) <= 5:
            parts.append(part)
        else:
            parts.append(part[:1].upper() + part[1:].lower() if part else "")
    return " ".join([p for p in parts if p]).strip()


def guess_seed_category(term: str) -> str:
    """Heuristic mapping into stage-1 seed categories."""
    n = (term or "").strip().lower()
    if not n:
        return "Medicinal Herbs"
    if any(w in n for w in ("starter", "scoby", "kefir", "culture", "yogurt", "kombucha", "sourdough")):
        return "Fermentation Starters"
    if "clay" in n:
        return "Clays"
    if any(w in n for w in ("salt", "epsom")):
        return "Salts"
    if any(w in n for w in ("acid", "vinegar")):
        return "Acids"
    if "sugar" in n:
        return "Sugars"
    if any(w in n for w in ("honey", "molasses", "maple", "agave", "syrup")):
        return "Liquid Sweeteners"
    if any(w in n for w in ("mica", "spirulina", "annatto", "charcoal", "oxide", "ultramarine")):
        return "Colorants"
    if "gum" in n or any(w in n for w in ("xanthan", "guar")):
        return "Gums"
    if any(w in n for w in ("frankincense", "myrrh", "damar", "copal", "benzoin")):
        return "Resins"
    if any(w in n for w in ("wax", "beeswax", "candelilla", "carnauba")):
        return "Waxes"
    if "root" in n:
        return "Roots"
    if "bark" in n:
        return "Barks"
    if any(w in n for w in ("rose", "lavender", "hibiscus", "jasmine")):
        return "Flowers"
    if any(w in n for w in ("cinnamon", "turmeric", "ginger", "clove", "vanilla", "pepper")):
        return "Spices"
    return "Medicinal Herbs"


def _load_tgsc(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def _load_cosing(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def normalize_sources(tgsc_path: Path, cosing_path: Path) -> List[Dict[str, Any]]:
    """Aggregate source rows into normalized base-term records."""
    merged: Dict[str, Dict[str, Any]] = {}

    for row in _load_tgsc(tgsc_path):
        base = normalize_base_name(row.get("common_name") or "")
        if not base:
            continue
        rec = merged.setdefault(
            base,
            {
                "term": base,
                "seed_category": guess_seed_category(base),
                "botanical_name": "",
                "inci_name": "",
                "cas_number": "",
                "description": "",
                "sources": [],
            },
        )
        if not rec["botanical_name"]:
            rec["botanical_name"] = (row.get("botanical_name") or "").strip()
        if not rec["cas_number"]:
            rec["cas_number"] = (row.get("cas_number") or "").strip()
        if not rec["description"]:
            rec["description"] = (row.get("description") or "").strip()
        rec["sources"].append(
            {
                "source": "tgsc",
                "raw_name": (row.get("common_name") or "").strip(),
                "category": (row.get("category") or "").strip(),
                "url": (row.get("url") or "").strip(),
                "synonyms": (row.get("synonyms") or "").strip(),
            }
        )

    for row in _load_cosing(cosing_path):
        raw_inci = (row.get("INCI name") or row.get("INCI Name") or "").strip()
        base = normalize_base_name(raw_inci)
        if not base:
            continue
        rec = merged.setdefault(
            base,
            {
                "term": base,
                "seed_category": guess_seed_category(base),
                "botanical_name": "",
                "inci_name": "",
                "cas_number": "",
                "description": "",
                "sources": [],
            },
        )
        if not rec["inci_name"]:
            rec["inci_name"] = raw_inci
        cas = (row.get("CAS No") or "").strip()
        if cas and not rec["cas_number"]:
            rec["cas_number"] = cas
        if not rec["description"]:
            rec["description"] = (row.get("Chem/IUPAC Name / Description") or "").strip()
        rec["sources"].append(
            {
                "source": "cosing",
                "raw_name": raw_inci,
                "cas_number": cas,
                "function": (row.get("Function") or "").strip(),
                "description": (row.get("Chem/IUPAC Name / Description") or "").strip(),
            }
        )

    out: List[Dict[str, Any]] = []
    for term in sorted(merged.keys(), key=lambda s: (s.casefold(), s)):
        rec = merged[term]
        sources_json = json.dumps({"sources": rec["sources"]}, ensure_ascii=False, sort_keys=True)
        out.append(
            {
                "term": rec["term"],
                "seed_category": rec["seed_category"],
                "botanical_name": rec["botanical_name"],
                "inci_name": rec["inci_name"],
                "cas_number": rec["cas_number"],
                "description": rec["description"],
                "sources_json": sources_json,
                "source_count": len(rec["sources"]),
            }
        )
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "term",
        "seed_category",
        "botanical_name",
        "inci_name",
        "cas_number",
        "description",
        "source_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") or "" for k in fieldnames})


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Normalize ingredient source CSVs into base terms")
    parser.add_argument("--tgsc", default=str(DATA_SOURCES_DIR / "tgsc_ingredients.csv"))
    parser.add_argument("--cosing", default=str(DATA_SOURCES_DIR / "cosing.csv"))
    parser.add_argument("--out", default=str(OUTPUT_CSV))
    parser.add_argument("--no-db", action="store_true", help="Do not upsert into compiler_state.db")
    args = parser.parse_args(argv)

    tgsc_path = Path(args.tgsc).resolve()
    cosing_path = Path(args.cosing).resolve()
    out_path = Path(args.out).resolve()

    rows = normalize_sources(tgsc_path, cosing_path)
    write_csv(out_path, rows)
    LOGGER.info("Wrote %s normalized terms to %s", len(rows), out_path)

    if not args.no_db:
        inserted = database_manager.upsert_normalized_terms(rows)
        LOGGER.info("Upserted normalized_terms into DB (new=%s)", inserted)


if __name__ == "__main__":
    main()

