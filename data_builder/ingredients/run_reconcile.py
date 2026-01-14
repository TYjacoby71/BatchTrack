"""Standalone reconciliation script that avoids import chain issues."""
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

MODIFIER_TRIGGER_WORDS = {
    "peg-", "ppg-", "polyglyceryl-", "glycereth-",
    "amidopropyl", "amide", "betaine", "hydroxysultaine",
    "trimonium", "dimethylamine", "amphoacetate",
    "esters", "ester", "glyceride", "glycerides",
    "butterate", "crosspolymer", "dimethicone",
    "sulfate", "phosphate", "chloride", "oxide",
    "oleate", "stearate", "laurate", "myristate",
}

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

BASE_INGREDIENT_PATTERNS = {
    "shea": "Shea",
    "cocoa": "Cocoa",
    "mango": "Mango",
    "coconut": "Coconut",
    "coco": "Coconut",
    "coca": "Coconut",
    "coc": "Coconut",
    "almond": "Almond",
    "argan": "Argan",
    "avocado": "Avocado",
    "avocad": "Avocado",
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
    "canol": "Canola",
    "rapeseed": "Rapeseed",
    "sesame": "Sesame",
    "flax": "Flax",
    "linseed": "Flax",
    "macadamia": "Macadamia",
    "kukui": "Kukui",
    "meadowfoam": "Meadowfoam",
    "borage": "Borage",
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
    "laur": "Lauric Acid",
    "myrist": "Myristic Acid",
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
    "hippophae rhamnoides": "Sea Buckthorn",
    "cannabis": "Hemp",
    "acryl": "Acrylic",
    "acet": "Acetic Acid",
    "form": "Formic Acid",
    "dimer dilinole": "Dimer Dilinoleic Acid",
}


def _normalize(term: str) -> str:
    return re.sub(r"\s+", " ", (term or "").lower().strip())


def _has_modifier(term: str) -> bool:
    t = _normalize(term)
    return any(mod in t for mod in MODIFIER_TRIGGER_WORDS)


def _extract_base_and_variation(term: str) -> tuple[str | None, str | None]:
    if not term:
        return None, None
    
    t = _normalize(term)
    original = term.strip()
    
    if t.startswith("peg-") or t.startswith("ppg-"):
        m = re.match(r"(peg-\d+|ppg-\d+)\s+(.+?)\s+(butter|oil)\s+(.+)", t, re.IGNORECASE)
        if m:
            base_ingredient = m.group(2).strip().title()
            variation = f"{m.group(1).upper()} {m.group(3).title()} {m.group(4).title()}"
            return base_ingredient, variation
    
    if "butteramido" in t or "butteramide" in t:
        m = re.match(r"(.+?)(butter)(amido.+|amide.+)", t, re.IGNORECASE)
        if m:
            base = m.group(1).strip().title()
            variation = f"Butter{m.group(3).title()}"
            return base, variation
    
    for suffix in MODIFIER_SUFFIXES:
        if t.endswith(suffix):
            base_part = original[:-(len(suffix))].strip()
            variation = suffix.title()
            if base_part:
                for pat_key, base_name in sorted(BASE_INGREDIENT_PATTERNS.items(), key=lambda x: -len(x[0])):
                    if base_part.lower().startswith(pat_key):
                        return base_name, variation
                return base_part.title(), variation
    
    if " butter " in f" {t} ":
        parts = re.split(r"\s+butter\s+", t, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[1]:
            base = parts[0].strip()
            for pat_key, base_name in sorted(BASE_INGREDIENT_PATTERNS.items(), key=lambda x: -len(x[0])):
                if base.lower() == pat_key or base.lower().endswith(pat_key):
                    base = base_name
                    break
            else:
                base = base.title()
            # Include "Butter" in base term so it matches the correct parent cluster
            base = f"{base} Butter"
            variation = parts[1].strip().title()
            if _has_modifier(parts[1]):
                return base, variation
    
    if " oil " in f" {t} ":
        parts = re.split(r"\s+oil\s+", t, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[1]:
            base = parts[0].strip()
            for pat_key, base_name in sorted(BASE_INGREDIENT_PATTERNS.items(), key=lambda x: -len(x[0])):
                if base.lower() == pat_key or base.lower().endswith(pat_key):
                    base = base_name
                    break
            else:
                base = base.title()
            # Include "Oil" in base term so it matches the correct parent cluster
            base = f"{base} Oil"
            variation = parts[1].strip().title()
            if _has_modifier(parts[1]):
                return base, variation
    
    for pat_key, base_name in sorted(BASE_INGREDIENT_PATTERNS.items(), key=lambda x: -len(x[0])):
        if t.startswith(pat_key) and _has_modifier(t):
            suffix_start = len(pat_key)
            variation_part = original[suffix_start:].strip()
            if variation_part:
                return base_name, variation_part.title()
    
    return None, None


def _find_parent_cluster(conn: sqlite3.Connection, base_term: str) -> str | None:
    if not base_term:
        return None
    
    base_lower = base_term.lower().strip()
    cur = conn.cursor()
    
    # First try exact match on canonical_term
    cur.execute(
        "SELECT cluster_id, canonical_term FROM source_definitions WHERE LOWER(canonical_term) = ?",
        (base_lower,)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    
    # For "X Butter" or "X Oil", also search for just "X" as canonical
    base_parts = base_lower.split()
    if len(base_parts) >= 2 and base_parts[-1] in ('butter', 'oil', 'wax', 'seed', 'leaf', 'fruit', 'nut'):
        # Try "Shea Butter" first, then fallback to "Shea"
        product_type = base_parts[-1]
        ingredient_name = ' '.join(base_parts[:-1])
        
        # Look for cluster with matching product type (e.g., "Shea Butter")
        cur.execute(
            "SELECT cluster_id, canonical_term FROM source_definitions WHERE LOWER(canonical_term) = ?",
            (base_lower,)
        )
        row = cur.fetchone()
        if row:
            return row[0]
        
        # Look for cluster that ends with product type (e.g., canonical_term = "Shea Butter")
        cur.execute(
            "SELECT cluster_id, canonical_term FROM source_definitions WHERE LOWER(canonical_term) LIKE ? AND parent_cluster_id IS NULL",
            (f"%{ingredient_name} {product_type}%",)
        )
        candidates = cur.fetchall()
        for cluster_id, ct in candidates:
            ct_norm = _normalize(ct or "")
            if not _has_modifier(ct_norm):
                return cluster_id
    
    cur.execute(
        "SELECT cluster_id, canonical_term FROM source_definitions WHERE LOWER(canonical_term) LIKE ? AND parent_cluster_id IS NULL",
        (f"%{base_lower}%",)
    )
    candidates = cur.fetchall()
    
    for cluster_id, ct in candidates:
        ct_norm = _normalize(ct or "")
        if ct_norm == base_lower:
            return cluster_id
    
    # For "Shea Butter", match clusters where canonical_term is "Shea Butter"
    for cluster_id, ct in candidates:
        ct_norm = _normalize(ct or "")
        if ct_norm == base_lower or ct_norm == base_lower.replace(' butter', '') or ct_norm == base_lower.replace(' oil', ''):
            return cluster_id
    
    for cluster_id, ct in candidates:
        ct_norm = _normalize(ct or "")
        if not _has_modifier(ct_norm) and base_lower in ct_norm:
            words = ct_norm.split()
            if len(words) <= 3:
                return cluster_id
    
    return None


def reconcile_derivatives(db_path: str, dry_run: bool = False) -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    stats = {
        "total_definitions": 0,
        "derivatives_found": 0,
        "linked_to_existing": 0,
        "created_base_clusters": 0,
        "updated": 0,
        "skipped": 0,
        "examples": [],
    }
    
    cur.execute("SELECT cluster_id, canonical_term, parent_cluster_id FROM source_definitions")
    all_defs = cur.fetchall()
    stats["total_definitions"] = len(all_defs)
    
    created_bases: dict[str, str] = {}
    
    for cluster_id, term, existing_parent in all_defs:
        if existing_parent:
            stats["skipped"] += 1
            continue
        
        base_term, variation = _extract_base_and_variation(term or "")
        
        if not base_term or not variation:
            continue
        
        stats["derivatives_found"] += 1
        
        parent_id = _find_parent_cluster(conn, base_term)
        
        if not parent_id:
            new_cluster_id = f"base:{base_term.lower().replace(' ', '_')}"
            if base_term not in created_bases:
                created_bases[base_term] = new_cluster_id
                stats["created_base_clusters"] += 1
                
                if not dry_run:
                    cur.execute("""
                        INSERT OR IGNORE INTO source_definitions 
                        (cluster_id, canonical_term, origin, ingredient_category, confidence, 
                         reason, item_count, sample_item_keys_json, member_cas_json, 
                         member_inci_samples_json, reconciled_term, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        new_cluster_id, base_term, "Plant-Derived", "Herbs", 50,
                        "synthetic_base_for_derivatives", 0, "[]", "[]", "[]",
                        base_term, datetime.utcnow().isoformat()
                    ))
            parent_id = created_bases[base_term]
        else:
            stats["linked_to_existing"] += 1
        
        if not dry_run:
            cur.execute("""
                UPDATE source_definitions 
                SET reconciled_term = ?, reconciled_variation = ?, parent_cluster_id = ?
                WHERE cluster_id = ?
            """, (base_term, variation, parent_id, cluster_id))
            stats["updated"] += 1
        
        if len(stats["examples"]) < 20:
            stats["examples"].append({
                "term": term,
                "base": base_term,
                "variation": variation,
                "parent": parent_id
            })
    
    if not dry_run:
        conn.commit()
    conn.close()
    
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="output/Final DB.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    LOGGER.info(f"Running reconciliation (dry_run={args.dry_run})")
    stats = reconcile_derivatives(args.db, dry_run=args.dry_run)
    
    LOGGER.info("=== Results ===")
    for k, v in stats.items():
        if k != "examples":
            LOGGER.info(f"  {k}: {v}")
    
    LOGGER.info("=== Examples ===")
    for ex in stats.get("examples", []):
        LOGGER.info(f"  {ex['term']} -> base:{ex['base']}, var:{ex['variation']}")
