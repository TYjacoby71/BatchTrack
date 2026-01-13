#!/usr/bin/env python3
"""
Deterministic seed item compiler.

Compiles seed-derived terms through the compilation pipeline WITHOUT calling AI.
Follows the same rules and schema as ai_worker but with deterministic mappings.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

FINAL_DB_PATH = Path(__file__).parent / "output" / "Final DB.db"

CATEGORY_MAP = {
    "Agave Nectar": "Liquid Sweeteners",
    "Flour": "Grains",
    "Almonds": "Nuts",
    "Aloe Vera 10x": "Herbs",
    "Alpha Arbutin": "Synthetic - Other",
    "Apple Cider Vinegar": "Acids",
    "Apricot Kernel Meal": "Nuts",
    "Argan": "Seeds",
    "BTMS-50": "Synthetic - Surfactants",
    "Bamboo & Coconut": "Synthetic - Other",
}

COMMON_NAME_MAP = {
    "Agave Nectar": "Agave Nectar",
    "Flour": "Flour",
    "Almonds": "Almonds",
    "Aloe Vera 10x": "Aloe Vera 10x Concentrate",
    "Alpha Arbutin": "Alpha Arbutin",
    "Apple Cider Vinegar": "Apple Cider Vinegar",
    "Apricot Kernel Meal": "Apricot Kernel Meal",
    "Argan": "Argan Oil",
    "BTMS-50": "BTMS-50 (Behentrimonium Methosulfate)",
    "Bamboo & Coconut": "Bamboo & Coconut Fragrance Oil",
}

DESCRIPTION_MAP = {
    "Agave Nectar": {
        "short": "A natural liquid sweetener derived from the agave plant.",
        "detailed": "Agave nectar is a natural sweetener produced from the sap of the agave plant. It has a lower glycemic index than sugar and dissolves easily in cold liquids, making it popular for beverages and baked goods."
    },
    "Flour": {
        "short": "Finely milled grain powder used as a primary baking ingredient.",
        "detailed": "Flour is a finely milled powder made from grains. Different varieties (all-purpose, bread, whole wheat, etc.) have varying protein content and are suited for different baking applications."
    },
    "Almonds": {
        "short": "Nutrient-rich tree nuts used whole, sliced, or ground.",
        "detailed": "Almonds are edible seeds from the almond tree. They are rich in healthy fats, protein, fiber, and vitamin E. Used in baking, confectionery, and as a snack."
    },
    "Aloe Vera 10x": {
        "short": "A concentrated aqueous extract of aloe vera leaf.",
        "detailed": "Aloe Vera 10x Concentrate is a potent aqueous extract containing 10 times the concentration of standard aloe vera gel. Used in skincare formulations for its soothing and moisturizing properties."
    },
    "Alpha Arbutin": {
        "short": "A synthetic skin-brightening active ingredient.",
        "detailed": "Alpha Arbutin is a biosynthetic active ingredient that inhibits tyrosinase, reducing melanin production. It is used in skincare formulations for brightening and evening skin tone."
    },
    "Apple Cider Vinegar": {
        "short": "A fermented vinegar made from apple juice.",
        "detailed": "Apple cider vinegar is produced by fermenting apple juice. It contains acetic acid and is used in culinary applications, as a hair rinse, and in various household and personal care applications."
    },
    "Apricot Kernel Meal": {
        "short": "Ground apricot seeds used as a gentle exfoliant.",
        "detailed": "Apricot kernel meal is made from finely ground apricot pits. It is used as a natural exfoliant in skincare formulations and can also be used in baking for added nutrition."
    },
    "Argan": {
        "short": "A nourishing oil pressed from Moroccan argan tree nuts.",
        "detailed": "Argan oil is extracted from the kernels of the argan tree native to Morocco. Rich in vitamin E and fatty acids, it is prized for its moisturizing and anti-aging properties in skincare and haircare."
    },
    "BTMS-50": {
        "short": "A conditioning emulsifier for hair and skin products.",
        "detailed": "BTMS-50 (Behentrimonium Methosulfate and Cetyl Alcohol) is a plant-derived conditioning emulsifier. It creates stable emulsions with excellent conditioning properties, commonly used in hair conditioners and lotions."
    },
    "Bamboo & Coconut": {
        "short": "A fragrance oil with fresh bamboo and tropical coconut notes.",
        "detailed": "Bamboo & Coconut fragrance oil combines fresh green bamboo notes with creamy tropical coconut. Popular in candles, soaps, and personal care products for its clean, spa-like scent profile."
    },
}

ORIGIN_MAP = {
    "Agave Nectar": "Plant-Derived",
    "Flour": "Plant-Derived",
    "Almonds": "Plant-Derived",
    "Aloe Vera 10x": "Plant-Derived",
    "Alpha Arbutin": "Synthetic",
    "Apple Cider Vinegar": "Fermentation",
    "Apricot Kernel Meal": "Plant-Derived",
    "Argan": "Plant-Derived",
    "BTMS-50": "Plant-Derived",
    "Bamboo & Coconut": "Synthetic",
}

REFINEMENT_MAP = {
    "Flour": "Milled",
}

VARIATION_BYPASS_TERMS = {
    "Apple Cider Vinegar",
}

FUNCTIONS_MAP = {
    "Agave Nectar": ["Sweetener", "Humectant"],
    "Flour": ["Thickener", "Binder", "Structure"],
    "Almonds": ["Exfoliant", "Protein Source", "Flavoring"],
    "Aloe Vera 10x": ["Moisturizer", "Soothing Agent", "Humectant"],
    "Alpha Arbutin": ["Skin Brightener", "Tyrosinase Inhibitor"],
    "Apple Cider Vinegar": ["pH Adjuster", "Clarifying Agent"],
    "Apricot Kernel Meal": ["Exfoliant", "Absorbent"],
    "Argan": ["Emollient", "Moisturizer", "Anti-oxidant"],
    "BTMS-50": ["Emulsifier", "Conditioner", "Detangler"],
    "Bamboo & Coconut": ["Fragrance"],
}

APPLICATIONS_MAP = {
    "Agave Nectar": ["Baked Goods", "Beverages", "Confectionery", "Lip Products"],
    "Flour": ["Baked Goods", "Bread", "Pastry", "Cookies"],
    "Almonds": ["Baked Goods", "Confectionery", "Exfoliating Scrubs"],
    "Aloe Vera 10x": ["Lotion", "Cream", "Serum", "Gel", "After Sun"],
    "Alpha Arbutin": ["Serum", "Cream", "Lotion", "Toner"],
    "Apple Cider Vinegar": ["Hair Rinse", "Toner", "Culinary"],
    "Apricot Kernel Meal": ["Facial Scrub", "Body Scrub", "Soap"],
    "Argan": ["Lotion", "Cream", "Serum", "Hair Oil", "Soap"],
    "BTMS-50": ["Conditioner", "Lotion", "Cream", "Leave-in Treatment"],
    "Bamboo & Coconut": ["Candles", "Soap", "Lotion", "Body Wash"],
}


def build_item(term: str, variation: str, physical_form: str) -> Dict[str, Any]:
    """Build an item entry for the payload."""
    variation_bypass = term in VARIATION_BYPASS_TERMS
    
    if variation_bypass:
        item_name = COMMON_NAME_MAP.get(term, term)
        variation = ""
    elif variation:
        item_name = f"{COMMON_NAME_MAP.get(term, term)} ({variation})"
    else:
        item_name = COMMON_NAME_MAP.get(term, term)
    
    return {
        "item_name": item_name,
        "variation": variation or "",
        "physical_form": physical_form or "Liquid",
        "form_bypass": False,
        "variation_bypass": variation_bypass,
        "function_tags": FUNCTIONS_MAP.get(term, []),
        "applications": APPLICATIONS_MAP.get(term, []),
        "safety_tags": [],
        "sds_hazards": [],
        "specifications": {},
        "storage": {
            "temperature_celsius": {"min": 15, "max": 25},
            "humidity_percent": {"max": 60},
            "special_instructions": "Store in a cool, dry place."
        },
        "sourcing": {
            "common_origins": [],
            "certifications": [],
            "supply_risks": [],
            "sustainability_notes": ""
        },
        "synonyms": []
    }


def build_payload(term: str, variation: str, physical_form: str) -> Dict[str, Any]:
    """Build the full compiled payload for an ingredient term."""
    descs = DESCRIPTION_MAP.get(term, {"short": "", "detailed": ""})
    
    payload = {
        "ingredient": {
            "common_name": COMMON_NAME_MAP.get(term, term),
            "category": CATEGORY_MAP.get(term, "Herbs"),
            "botanical_name": "",
            "inci_name": "",
            "cas_number": "",
            "short_description": descs["short"],
            "detailed_description": descs["detailed"],
            "origin": {
                "regions": [],
                "source_material": "",
                "processing_methods": []
            },
            "primary_functions": FUNCTIONS_MAP.get(term, []),
            "regulatory_notes": [],
            "items": [build_item(term, variation, physical_form)],
            "taxonomy": {
                "color_profile": [],
                "scent_profile": [],
                "texture_profile": [],
                "compatible_processes": APPLICATIONS_MAP.get(term, []),
                "incompatible_processes": []
            },
            "documentation": {
                "references": [],
                "last_verified": datetime.now().strftime("%Y-%m-%d")
            }
        },
        "data_quality": {
            "confidence": 0.7,
            "caveats": ["Deterministic seed compilation - manual review recommended."]
        }
    }
    
    return payload


def compile_seed_items(terms: Optional[List[str]] = None, dry_run: bool = True) -> Dict[str, Any]:
    """Compile seed items into the ingredients table."""
    conn = sqlite3.connect(FINAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    if terms:
        placeholders = ",".join("?" * len(terms))
        query = f"""
            SELECT si.key, si.raw_name, si.derived_term, si.derived_variation, 
                   si.derived_physical_form, si.origin, si.merged_item_id
            FROM source_items si
            WHERE si.source = 'seed' AND si.derived_term IN ({placeholders})
            ORDER BY si.raw_name
        """
        cur.execute(query, terms)
    else:
        cur.execute("""
            SELECT si.key, si.raw_name, si.derived_term, si.derived_variation, 
                   si.derived_physical_form, si.origin, si.merged_item_id
            FROM source_items si
            WHERE si.source = 'seed'
            ORDER BY si.raw_name
            LIMIT 10
        """)
    
    rows = cur.fetchall()
    
    results = {
        "processed": 0,
        "inserted": 0,
        "skipped": 0,
        "errors": [],
        "compiled": []
    }
    
    for row in rows:
        term = row["derived_term"]
        variation = row["derived_variation"] or ""
        physical_form = row["derived_physical_form"] or ""
        origin = row["origin"] or "Plant-Derived"
        merged_item_id = row["merged_item_id"]
        
        if term not in CATEGORY_MAP:
            results["skipped"] += 1
            results["errors"].append(f"No mapping for term: {term}")
            continue
        
        cur.execute("SELECT term FROM ingredients WHERE term = ?", (term,))
        if cur.fetchone():
            results["skipped"] += 1
            results["errors"].append(f"Already exists: {term}")
            continue
        
        payload = build_payload(term, variation, physical_form)
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        
        category = CATEGORY_MAP.get(term, "Herbs")
        compiled_origin = ORIGIN_MAP.get(term, origin)
        
        results["compiled"].append({
            "term": term,
            "category": category,
            "origin": compiled_origin,
            "common_name": COMMON_NAME_MAP.get(term, term)
        })
        
        if not dry_run:
            cur.execute("""
                INSERT INTO ingredients (
                    term, seed_category, ingredient_category, origin,
                    botanical_name, inci_name, cas_number,
                    short_description, detailed_description,
                    prohibited_flag, gras_status, allergen_flag, colorant_flag,
                    payload_json, compiled_at, enumeration_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                term,
                category,
                category,
                compiled_origin,
                "",
                "",
                "",
                payload["ingredient"]["short_description"],
                payload["ingredient"]["detailed_description"],
                False,
                False,
                False,
                False,
                payload_json,
                datetime.now(),
                0
            ))
            
            cur.execute("""
                UPDATE merged_item_forms 
                SET compiled_specs_json = ?
                WHERE id = ?
            """, (payload_json, merged_item_id))
            
            results["inserted"] += 1
        
        results["processed"] += 1
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compile seed items deterministically")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without inserting")
    parser.add_argument("--commit", action="store_true", help="Actually insert into database")
    args = parser.parse_args()
    
    dry_run = not args.commit
    
    target_terms = list(CATEGORY_MAP.keys())
    
    print(f"Compiling {len(target_terms)} seed terms...")
    print(f"Mode: {'DRY RUN' if dry_run else 'COMMIT'}")
    print("-" * 60)
    
    results = compile_seed_items(terms=target_terms, dry_run=dry_run)
    
    print(f"\nResults:")
    print(f"  Processed: {results['processed']}")
    print(f"  Inserted: {results['inserted']}")
    print(f"  Skipped: {results['skipped']}")
    
    if results["compiled"]:
        print(f"\nCompiled terms:")
        for item in results["compiled"]:
            print(f"  - {item['term']} -> {item['category']} ({item['origin']})")
    
    if results["errors"]:
        print(f"\nErrors/Notes:")
        for err in results["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
