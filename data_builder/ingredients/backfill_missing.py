#!/usr/bin/env python3
"""Backfill missing fields (density, color, odor) in compiled items using AI."""

import json
import os
import sqlite3
import sys
import openai

DB_PATH = "data_builder/ingredients/output/Final DB.db"

openai.api_key = os.environ.get("OPENAI_API_KEY")

BACKFILL_PROMPT = """You are filling in missing ingredient data. Given the item info below, provide the missing fields.

Item: {item_name}
Term: {term}
Physical Form: {physical_form}
Variation: {variation}

Current data:
{current_data}

Fill in ONLY the fields marked as "Not Found". Use your training knowledge.
For density_g_ml: oils 0.85-0.95, butters 0.86-0.92, waxes 0.95-0.98, EO 0.85-1.05, extracts/hydrosols ~0.95-1.0
For color: describe the typical color (pale yellow, amber, brown, colorless, white, green, etc)
For odor_profile: describe the typical scent (woody, floral, herbaceous, spicy, warm, citrus, etc)

Return ONLY a JSON object with the fields to update. Example:
{{"density_g_ml": "0.92", "color": "pale yellow", "odor_profile": "mild herbal scent"}}

If you truly don't know a value, keep it as "Not Found". But most common ingredients ARE documented - use your knowledge!
"""

def get_items_needing_backfill(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT cci.id, cc.compiled_term, cci.derived_variation, cci.derived_physical_form, cci.item_json
        FROM compiled_cluster_items cci
        JOIN compiled_clusters cc ON cc.cluster_id = cci.cluster_id
        WHERE cci.item_status = 'done'
        AND (
            cci.item_json LIKE '%"density_g_ml": "Not Found"%'
            OR cci.item_json LIKE '%"color": "Not Found"%'
            OR cci.item_json LIKE '%"odor_profile": "Not Found"%'
        )
    """)
    return cur.fetchall()


def backfill_item(item_id, term, variation, physical_form, item_json_str):
    item_data = json.loads(item_json_str)
    item_name = item_data.get("item_name", f"{term} ({variation})")
    
    missing_fields = {}
    specs = item_data.get("specifications", {})
    if specs.get("density_g_ml") == "Not Found":
        missing_fields["density_g_ml"] = "Not Found"
    if item_data.get("color") == "Not Found":
        missing_fields["color"] = "Not Found"
    if item_data.get("odor_profile") == "Not Found":
        missing_fields["odor_profile"] = "Not Found"
    
    if not missing_fields:
        return None
    
    prompt = BACKFILL_PROMPT.format(
        item_name=item_name,
        term=term,
        physical_form=physical_form,
        variation=variation,
        current_data=json.dumps(missing_fields, indent=2)
    )
    
    client = openai.OpenAI(api_key=openai.api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a cosmetic/food ingredient expert. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=200
    )
    
    response_text = response.choices[0].message.content.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    
    updates = json.loads(response_text)
    
    changed = False
    if "density_g_ml" in updates and updates["density_g_ml"] != "Not Found":
        specs["density_g_ml"] = updates["density_g_ml"]
        item_data["specifications"] = specs
        changed = True
    if "color" in updates and updates["color"] != "Not Found":
        item_data["color"] = updates["color"]
        changed = True
    if "odor_profile" in updates and updates["odor_profile"] != "Not Found":
        item_data["odor_profile"] = updates["odor_profile"]
        changed = True
    
    if changed:
        return json.dumps(item_data, ensure_ascii=False)
    return None


def main():
    if not openai.api_key:
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    items = get_items_needing_backfill(conn)
    print(f"Found {len(items)} items needing backfill")
    
    updated = 0
    errors = 0
    
    for i, (item_id, term, variation, physical_form, item_json) in enumerate(items):
        try:
            print(f"[{i+1}/{len(items)}] {term} - {variation or 'base'}...", end=" ", flush=True)
            new_json = backfill_item(item_id, term, variation, physical_form, item_json)
            
            if new_json:
                cur = conn.cursor()
                cur.execute("UPDATE compiled_cluster_items SET item_json = ? WHERE id = ?", (new_json, item_id))
                conn.commit()
                print("UPDATED")
                updated += 1
            else:
                print("no changes")
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
    
    conn.close()
    print(f"\nDone! Updated: {updated}, Errors: {errors}, Skipped: {len(items) - updated - errors}")


if __name__ == "__main__":
    main()
