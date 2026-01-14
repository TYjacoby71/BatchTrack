"""Post-processing reconciliation for derivative ingredient clusters.

This module scans existing source_definitions and identifies derivative terms
(e.g., "Shea Butter Cetyl Esters") that should be linked to base term clusters
(e.g., "Shea"). It populates reconciled_term, reconciled_variation, and
parent_cluster_id fields without re-ingesting data.
"""
from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

try:
    from .database_manager import SourceDefinition, Base
except ImportError:
    from database_manager import SourceDefinition, Base

LOGGER = logging.getLogger(__name__)

MODIFIER_PATTERNS = [
    (r"\s+PEG-\d+\s+", "PEG-X"),
    (r"\s+POLYGLYCERYL-\d+\s+", "POLYGLYCERYL-X"),
    (r"\s+GLYCERETH-\d+\s+", "GLYCERETH-X"),
    (r"\s+PPG-\d+\s+", "PPG-X"),
    (r"\s+CETYL\s+ESTERS?$", "Cetyl Esters"),
    (r"\s+ETHYL\s+ESTERS?$", "Ethyl Esters"),
    (r"\s+DECYL\s+ESTERS?$", "Decyl Esters"),
    (r"\s+OLEYL\s+ESTERS?$", "Oleyl Esters"),
    (r"\s+GLYCERIDES?$", "Glycerides"),
    (r"\s+GLYCERIDE$", "Glyceride"),
    (r"\s+ESTERS$", "Esters"),
    (r"\s+CROSSPOLYMER$", "Crosspolymer"),
    (r"\s+DIMETHICONE\s+ESTERS$", "Dimethicone Esters"),
]

MODIFIER_SUFFIXES = [
    "amidopropyl betaine",
    "amidopropyl hydroxysultaine",
    "amidopropyl dimethylamine",
    "amidopropylamine oxide",
    "amidopropyltrimonium chloride",
    "amidopropyltrimonium methosulfate",
    "amide dea",
    "amide mea",
    "amide mipa",
    "amphoacetate",
    "butterate",
]

MODIFIER_TRIGGER_WORDS = {
    "peg-", "ppg-", "polyglyceryl-", "glycereth-",
    "amidopropyl", "amide", "betaine", "hydroxysultaine",
    "trimonium", "dimethylamine", "amphoacetate",
    "esters", "ester", "glyceride", "glycerides",
    "butterate", "crosspolymer", "dimethicone",
    "sulfate", "phosphate", "chloride", "oxide",
    "oleate", "stearate", "laurate", "myristate",
}

BASE_INGREDIENT_PATTERNS = {
    "shea": "Shea",
    "cocoa": "Cocoa",
    "mango": "Mango",
    "coconut": "Coconut",
    "coco": "Coconut",
    "almond": "Almond",
    "argan": "Argan",
    "avocado": "Avocado",
    "olive": "Olive",
    "sunflower": "Sunflower",
    "safflower": "Safflower",
    "castor": "Castor",
    "jojoba": "Jojoba",
    "hemp": "Hemp",
    "babassu": "Babassu",
    "palm": "Palm",
    "soy": "Soy",
    "corn": "Corn",
    "wheat": "Wheat",
    "rice": "Rice",
    "oat": "Oat",
    "canola": "Canola",
    "rapeseed": "Rapeseed",
    "sesame": "Sesame",
    "flax": "Flax",
    "linseed": "Flax",
    "macadamia": "Macadamia",
    "kukui": "Kukui",
    "meadowfoam": "Meadowfoam",
    "borage": "Borage",
    "evening primrose": "Evening Primrose",
    "rosehip": "Rosehip",
    "marula": "Marula",
    "moringa": "Moringa",
    "tamanu": "Tamanu",
    "cupuacu": "Cupuacu",
    "murumuru": "Murumuru",
    "tucuma": "Tucuma",
    "pracaxi": "Pracaxi",
    "bacuri": "Bacuri",
    "shorea": "Shorea",
    "sal": "Sal",
    "illipe": "Illipe",
    "cottonseed": "Cottonseed",
    "grapeseed": "Grapeseed",
    "apricot": "Apricot",
    "peach": "Peach",
    "plum": "Plum",
    "cherry": "Cherry",
    "walnut": "Walnut",
    "hazelnut": "Hazelnut",
    "pistachio": "Pistachio",
    "peanut": "Peanut",
    "carrot": "Carrot",
    "tomato": "Tomato",
    "camellia": "Camellia",
    "camelina": "Camelina",
    "chia": "Chia",
    "perilla": "Perilla",
    "tallow": "Tallow",
    "lard": "Lard",
    "lanolin": "Lanolin",
    "beeswax": "Beeswax",
    "carnauba": "Carnauba",
    "candelilla": "Candelilla",
    "laur": "Lauric Acid",
    "myrist": "Myristic Acid",
    "palm": "Palmitic Acid",
    "stear": "Stearic Acid",
    "ole": "Oleic Acid",
    "linole": "Linoleic Acid",
    "capry": "Caprylic Acid",
    "capr": "Capric Acid",
    "behen": "Behenic Acid",
    "eruc": "Erucic Acid",
    "isostear": "Isostearic Acid",
    "undecylen": "Undecylenic Acid",
    "ricin": "Ricinoleic Acid",
}


def _normalize_for_matching(term: str) -> str:
    """Normalize term for matching: lowercase, strip extra spaces."""
    return re.sub(r"\s+", " ", (term or "").lower().strip())


def _has_modifier(term: str) -> bool:
    """Check if term contains any modifier trigger words."""
    t = _normalize_for_matching(term)
    return any(mod in t for mod in MODIFIER_TRIGGER_WORDS)


def _extract_base_and_variation(term: str) -> tuple[str | None, str | None]:
    """Extract base term and variation from a derivative term.
    
    Returns (base_term, variation) or (None, None) if not a derivative.
    """
    if not term:
        return None, None
    
    t = _normalize_for_matching(term)
    original = term.strip()
    
    for suffix in MODIFIER_SUFFIXES:
        if t.endswith(suffix):
            base_part = original[:-(len(suffix))].strip()
            variation = suffix.title()
            if base_part:
                return base_part, variation
    
    if "butteramido" in t or "butteramide" in t:
        m = re.match(r"(.+?)\s*(butter)(amido.+|amide.+)", t, re.IGNORECASE)
        if m:
            base = m.group(1).strip().title()
            variation = f"Butter{m.group(3).title()}"
            return base, variation
    
    if " butter " in f" {t} ":
        parts = re.split(r"\s+butter\s+", t, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[1]:
            base = parts[0].strip().title()
            variation = f"Butter {parts[1].strip().title()}"
            if _has_modifier(parts[1]):
                return base, variation
    
    if " oil " in f" {t} ":
        parts = re.split(r"\s+oil\s+", t, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[1]:
            base = parts[0].strip().title()
            variation = f"Oil {parts[1].strip().title()}"
            if _has_modifier(parts[1]):
                return base, variation
    
    for pat_key, base_name in BASE_INGREDIENT_PATTERNS.items():
        if t.startswith(pat_key) and _has_modifier(t):
            suffix_start = t.find(pat_key) + len(pat_key)
            variation_part = original[suffix_start:].strip()
            if variation_part:
                return base_name, variation_part.title()
    
    return None, None


def _find_parent_cluster(session: Session, base_term: str) -> str | None:
    """Find existing cluster that matches base term."""
    if not base_term:
        return None
    
    base_lower = base_term.lower().strip()
    
    exact = session.query(SourceDefinition).filter(
        SourceDefinition.canonical_term.ilike(base_lower)
    ).first()
    if exact:
        return exact.cluster_id
    
    like_pattern = f"%{base_lower}%"
    candidates = session.query(SourceDefinition).filter(
        SourceDefinition.canonical_term.ilike(like_pattern)
    ).all()
    
    for c in candidates:
        ct = _normalize_for_matching(c.canonical_term or "")
        if ct == base_lower:
            return c.cluster_id
        if ct in (base_lower, f"{base_lower} butter", f"{base_lower} oil"):
            return c.cluster_id
    
    for c in candidates:
        ct = _normalize_for_matching(c.canonical_term or "")
        if not _has_modifier(ct) and base_lower in ct:
            words = ct.split()
            if len(words) <= 3:
                return c.cluster_id
    
    return None


def _create_base_cluster(session: Session, base_term: str) -> str:
    """Create a synthetic base cluster for a base term that doesn't exist."""
    cluster_id = f"base:{base_term.lower().replace(' ', '_')}"
    
    existing = session.query(SourceDefinition).filter(
        SourceDefinition.cluster_id == cluster_id
    ).first()
    if existing:
        return cluster_id
    
    new_def = SourceDefinition(
        cluster_id=cluster_id,
        canonical_term=base_term,
        botanical_key=None,
        origin="Plant-Derived",
        ingredient_category="Herbs",
        confidence=50,
        reason="synthetic_base_for_derivatives",
        item_count=0,
        sample_item_keys_json="[]",
        member_cas_json="[]",
        member_inci_samples_json="[]",
        reconciled_term=base_term,
        reconciled_variation=None,
        parent_cluster_id=None,
        created_at=datetime.utcnow(),
    )
    session.add(new_def)
    LOGGER.info(f"Created synthetic base cluster: {cluster_id} -> {base_term}")
    return cluster_id


def reconcile_derivatives(db_path: str, *, dry_run: bool = False) -> dict:
    """Main reconciliation pass: identify derivatives and link to base clusters."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    
    stats = {
        "total_definitions": 0,
        "derivatives_found": 0,
        "linked_to_existing": 0,
        "created_base_clusters": 0,
        "updated": 0,
        "skipped": 0,
    }
    
    with SessionLocal() as session:
        all_defs = session.query(SourceDefinition).all()
        stats["total_definitions"] = len(all_defs)
        
        created_bases: set[str] = set()
        
        for defn in all_defs:
            term = defn.canonical_term or ""
            
            if defn.parent_cluster_id:
                stats["skipped"] += 1
                continue
            
            base_term, variation = _extract_base_and_variation(term)
            
            if not base_term or not variation:
                continue
            
            stats["derivatives_found"] += 1
            
            parent_id = _find_parent_cluster(session, base_term)
            
            if not parent_id:
                if base_term not in created_bases:
                    if not dry_run:
                        parent_id = _create_base_cluster(session, base_term)
                    created_bases.add(base_term)
                    stats["created_base_clusters"] += 1
                else:
                    parent_id = f"base:{base_term.lower().replace(' ', '_')}"
            else:
                stats["linked_to_existing"] += 1
            
            if not dry_run:
                defn.reconciled_term = base_term
                defn.reconciled_variation = variation
                defn.parent_cluster_id = parent_id
                stats["updated"] += 1
            
            LOGGER.info(f"  {term} -> base:{base_term}, var:{variation}, parent:{parent_id}")
        
        if not dry_run:
            session.commit()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Reconcile derivative clusters to base terms")
    parser.add_argument("--db", type=str, default="output/Final DB.db", help="Path to database")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    
    db_path = Path(args.db)
    if not db_path.exists():
        LOGGER.error(f"Database not found: {db_path}")
        return
    
    LOGGER.info(f"Running reconciliation on {db_path} (dry_run={args.dry_run})")
    stats = reconcile_derivatives(str(db_path), dry_run=args.dry_run)
    
    LOGGER.info("=== Reconciliation Results ===")
    for k, v in stats.items():
        LOGGER.info(f"  {k}: {v}")


if __name__ == "__main__":
    main()
