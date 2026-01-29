"""AI Worker for researching and correcting common names.

Identifies ingredient definitions with duplicate common names and uses OpenAI
to research accurate, species-specific common names.

Usage:
    # Export items needing common name research
    python -m data_builder.ingredients.ai_worker_common_name export --limit 100
    
    # Submit batch to OpenAI
    python -m data_builder.ingredients.ai_worker_common_name submit --file exports/common_name_batch_xxx.jsonl
    
    # Check batch status
    python -m data_builder.ingredients.ai_worker_common_name status --batch-id batch_xxx
    
    # Import completed results
    python -m data_builder.ingredients.ai_worker_common_name import --batch-id batch_xxx
    
    # Direct processing (non-batch, for small sets)
    python -m data_builder.ingredients.ai_worker_common_name process --limit 10
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import openai

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

DB_PATH = Path(__file__).parent / "output" / "Final DB.db"

openai.api_key = os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = 0.1


SYSTEM_PROMPT = """You are a botanical and cosmetic ingredient expert. Your task is to provide the accurate, 
species-specific common name for ingredients based on their scientific/botanical name.

Rules:
1. Provide the most widely-recognized common name for the specific species
2. Be species-specific, not genus-level (e.g., "Balsam Fir" for Abies balsamea, not just "Fir")
3. If multiple common names exist, prefer the one most used in cosmetics/personal care industry
4. For chemical derivatives, provide a descriptive common name based on the source
5. Return "Unknown" only if truly obscure with no established common name

Respond with JSON only: {"common_name": "Accurate Common Name", "confidence": "high|medium|low", "notes": "optional notes"}"""


def get_db() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH))


def find_duplicate_common_names() -> list[dict]:
    """Find common names shared across multiple distinct ingredient definitions."""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT c.common_name,
               COUNT(DISTINCT i.derived_term) as unique_definitions
        FROM compiled_cluster_items i
        JOIN compiled_clusters c ON i.cluster_id = c.cluster_id
        WHERE c.common_name IS NOT NULL 
          AND c.common_name != '' 
          AND c.common_name != 'N/A'
          AND c.common_name != 'Not Found'
          AND i.derived_term != c.common_name
          AND LOWER(i.derived_term) NOT LIKE '%' || LOWER(c.common_name) || '%'
        GROUP BY c.common_name
        HAVING unique_definitions > 1
        ORDER BY unique_definitions DESC
    ''')
    
    duplicates = []
    for row in cur.fetchall():
        duplicates.append({
            "common_name": row[0],
            "definition_count": row[1]
        })
    
    conn.close()
    return duplicates


def get_definitions_for_common_name(common_name: str) -> list[dict]:
    """Get all ingredient definitions that share a common name."""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT DISTINCT 
            i.derived_term,
            c.botanical_name,
            c.inci_name,
            c.cas_number,
            c.origin,
            c.ingredient_category,
            c.cluster_id
        FROM compiled_cluster_items i
        JOIN compiled_clusters c ON i.cluster_id = c.cluster_id
        WHERE c.common_name = ?
        AND i.derived_term != c.common_name
        AND LOWER(i.derived_term) NOT LIKE '%' || LOWER(c.common_name) || '%'
        ORDER BY i.derived_term
    ''', (common_name,))
    
    definitions = []
    for row in cur.fetchall():
        definitions.append({
            "derived_term": row[0],
            "botanical_name": row[1],
            "inci_name": row[2],
            "cas_number": row[3],
            "origin": row[4],
            "category": row[5],
            "cluster_id": row[6],
        })
    
    conn.close()
    return definitions


def build_prompt_for_definition(definition: dict, current_common_name: str) -> str:
    """Build a prompt to research the correct common name for a definition."""
    prompt = f"""Research the accurate common name for this cosmetic/botanical ingredient:

Term: {definition['derived_term']}
Botanical Name: {definition.get('botanical_name') or 'Not specified'}
INCI Name: {definition.get('inci_name') or 'Not specified'}
CAS Number: {definition.get('cas_number') or 'Not specified'}
Origin: {definition.get('origin') or 'Not specified'}
Category: {definition.get('category') or 'Not specified'}

Current (possibly incorrect) common name: {current_common_name}

Provide the most accurate, species-specific common name for this ingredient.
If this is a botanical species, provide the species-specific common name (not genus-level).
For example:
- Abies balsamea → "Balsam Fir" (not just "Fir" or "Silver Fir")
- Lavandula angustifolia → "English Lavender" or "True Lavender"
- Artemisia absinthium → "Wormwood" or "Absinth Wormwood"

Respond with JSON: {{"common_name": "...", "confidence": "high|medium|low", "notes": "..."}}"""
    
    return prompt


def get_all_duplicate_definitions() -> list[dict]:
    """Get all definitions with duplicate common names in a single query."""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        WITH duplicate_names AS (
            SELECT c.common_name
            FROM compiled_cluster_items i
            JOIN compiled_clusters c ON i.cluster_id = c.cluster_id
            WHERE c.common_name IS NOT NULL 
              AND c.common_name != '' 
              AND c.common_name != 'N/A'
              AND c.common_name != 'Not Found'
              AND i.derived_term != c.common_name
              AND LOWER(i.derived_term) NOT LIKE '%' || LOWER(c.common_name) || '%'
            GROUP BY c.common_name
            HAVING COUNT(DISTINCT i.derived_term) > 1
        )
        SELECT DISTINCT 
            i.derived_term,
            c.botanical_name,
            c.inci_name,
            c.cas_number,
            c.origin,
            c.ingredient_category,
            c.cluster_id,
            c.common_name
        FROM compiled_cluster_items i
        JOIN compiled_clusters c ON i.cluster_id = c.cluster_id
        WHERE c.common_name IN (SELECT common_name FROM duplicate_names)
          AND i.derived_term != c.common_name
          AND LOWER(i.derived_term) NOT LIKE '%' || LOWER(c.common_name) || '%'
        ORDER BY c.common_name, i.derived_term
    ''')
    
    definitions = []
    for row in cur.fetchall():
        definitions.append({
            "derived_term": row[0],
            "botanical_name": row[1],
            "inci_name": row[2],
            "cas_number": row[3],
            "origin": row[4],
            "category": row[5],
            "cluster_id": row[6],
            "current_common_name": row[7],
        })
    
    conn.close()
    return definitions


def export_all_batches(batch_size: int = 500) -> list[Path]:
    """Export ALL definitions needing common name research in batches of batch_size."""
    LOGGER.info("Fetching all duplicate definitions...")
    all_items = get_all_duplicate_definitions()
    
    if not all_items:
        LOGGER.info("No duplicate common names found")
        return []
    
    LOGGER.info(f"Total definitions to export: {len(all_items)}")
    
    output_files = []
    batch_num = 1
    
    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i + batch_size]
        output_file = EXPORTS_DIR / f"common_name_export_{batch_num}.jsonl"
        
        with open(output_file, "w") as f:
            for defn in batch:
                prompt = build_prompt_for_definition(defn, defn["current_common_name"])
                
                request = {
                    "custom_id": f"cn_{defn['cluster_id']}_{defn['derived_term'][:50]}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL_NAME,
                        "temperature": TEMPERATURE,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"}
                    }
                }
                
                f.write(json.dumps(request) + "\n")
        
        LOGGER.info(f"Exported batch {batch_num}: {len(batch)} items to {output_file}")
        output_files.append(output_file)
        batch_num += 1
    
    LOGGER.info(f"Created {len(output_files)} batch files")
    return output_files


def export_batch(limit: int = 100) -> Path:
    """Export definitions needing common name research to JSONL for batch processing."""
    duplicates = find_duplicate_common_names()
    
    if not duplicates:
        LOGGER.info("No duplicate common names found")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORTS_DIR / f"common_name_batch_{timestamp}.jsonl"
    
    count = 0
    with open(output_file, "w") as f:
        for dup in duplicates:
            if count >= limit:
                break
                
            definitions = get_definitions_for_common_name(dup["common_name"])
            
            for defn in definitions:
                if count >= limit:
                    break
                    
                prompt = build_prompt_for_definition(defn, dup["common_name"])
                
                request = {
                    "custom_id": f"cn_{defn['cluster_id']}_{defn['derived_term'][:50]}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL_NAME,
                        "temperature": TEMPERATURE,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"}
                    }
                }
                
                f.write(json.dumps(request) + "\n")
                count += 1
    
    LOGGER.info(f"Exported {count} items to {output_file}")
    return output_file


def submit_batch(file_path: str) -> str:
    """Submit a JSONL file to OpenAI Batch API."""
    client = openai.OpenAI()
    
    with open(file_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")
    
    LOGGER.info(f"Uploaded file: {file_obj.id}")
    
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"purpose": "common_name_research"}
    )
    
    LOGGER.info(f"Created batch: {batch.id}")
    LOGGER.info(f"Status: {batch.status}")
    
    return batch.id


def submit_all_batches() -> list[str]:
    """Submit all common_name_export_*.jsonl files to OpenAI."""
    export_files = sorted(EXPORTS_DIR.glob("common_name_export_*.jsonl"))
    
    if not export_files:
        LOGGER.error("No common_name_export files found. Run export-all first.")
        return []
    
    batch_ids = []
    for file_path in export_files:
        LOGGER.info(f"Submitting {file_path.name}...")
        try:
            batch_id = submit_batch(str(file_path))
            batch_ids.append(batch_id)
            time.sleep(1)
        except Exception as e:
            LOGGER.error(f"Failed to submit {file_path.name}: {e}")
    
    LOGGER.info(f"Submitted {len(batch_ids)} batches")
    
    batch_ids_file = EXPORTS_DIR / "common_name_batch_ids.json"
    with open(batch_ids_file, "w") as f:
        json.dump(batch_ids, f, indent=2)
    LOGGER.info(f"Saved batch IDs to {batch_ids_file}")
    
    return batch_ids


def check_status(batch_id: str) -> dict:
    """Check the status of a batch job."""
    client = openai.OpenAI()
    batch = client.batches.retrieve(batch_id)
    
    status = {
        "id": batch.id,
        "status": batch.status,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "failed_at": batch.failed_at,
        "request_counts": batch.request_counts,
        "output_file_id": batch.output_file_id,
        "error_file_id": batch.error_file_id,
    }
    
    LOGGER.info(f"Batch {batch_id}: {batch.status}")
    if batch.request_counts:
        LOGGER.info(f"  Completed: {batch.request_counts.completed}/{batch.request_counts.total}")
        LOGGER.info(f"  Failed: {batch.request_counts.failed}")
    
    return status


def import_results(batch_id: str) -> int:
    """Import completed batch results and update database."""
    client = openai.OpenAI()
    batch = client.batches.retrieve(batch_id)
    
    if batch.status != "completed":
        LOGGER.error(f"Batch not completed. Status: {batch.status}")
        return 0
    
    if not batch.output_file_id:
        LOGGER.error("No output file available")
        return 0
    
    content = client.files.content(batch.output_file_id)
    
    results_file = EXPORTS_DIR / f"common_name_results_{batch_id}.jsonl"
    with open(results_file, "wb") as f:
        f.write(content.read())
    
    LOGGER.info(f"Downloaded results to {results_file}")
    
    conn = get_db()
    cur = conn.cursor()
    updated = 0
    
    with open(results_file, "r") as f:
        for line in f:
            try:
                result = json.loads(line)
                custom_id = result.get("custom_id", "")
                
                if not custom_id.startswith("cn_"):
                    continue
                
                parts = custom_id[3:].split("_", 1)
                if len(parts) < 2:
                    continue
                    
                cluster_id = parts[0]
                
                response = result.get("response", {})
                body = response.get("body", {})
                choices = body.get("choices", [])
                
                if not choices:
                    continue
                
                content = choices[0].get("message", {}).get("content", "")
                
                try:
                    data = json.loads(content)
                    new_common_name = data.get("common_name")
                    confidence = data.get("confidence", "low")
                    
                    if new_common_name and new_common_name.lower() not in ["unknown", "n/a", "not found"]:
                        cur.execute('''
                            UPDATE compiled_clusters 
                            SET common_name = ?,
                                data_quality_notes = COALESCE(data_quality_notes, '') || 
                                    ' | AI common name update (' || ? || '): ' || datetime('now')
                            WHERE cluster_id = ?
                        ''', (new_common_name, confidence, cluster_id))
                        
                        if cur.rowcount > 0:
                            updated += 1
                            LOGGER.info(f"Updated {cluster_id}: {new_common_name} ({confidence})")
                            
                except json.JSONDecodeError:
                    LOGGER.warning(f"Failed to parse response for {custom_id}")
                    
            except Exception as e:
                LOGGER.error(f"Error processing result: {e}")
    
    conn.commit()
    conn.close()
    
    LOGGER.info(f"Updated {updated} common names")
    return updated


def process_direct(limit: int = 10) -> int:
    """Process items directly without batch API (for small sets)."""
    client = openai.OpenAI()
    
    duplicates = find_duplicate_common_names()
    
    if not duplicates:
        LOGGER.info("No duplicate common names found")
        return 0
    
    conn = get_db()
    cur = conn.cursor()
    updated = 0
    processed = 0
    
    for dup in duplicates:
        if processed >= limit:
            break
            
        definitions = get_definitions_for_common_name(dup["common_name"])
        
        for defn in definitions:
            if processed >= limit:
                break
            
            prompt = build_prompt_for_definition(defn, dup["common_name"])
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    temperature=TEMPERATURE,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                data = json.loads(content)
                
                new_common_name = data.get("common_name")
                confidence = data.get("confidence", "low")
                
                if new_common_name and new_common_name.lower() not in ["unknown", "n/a", "not found"]:
                    cur.execute('''
                        UPDATE compiled_clusters 
                        SET common_name = ?,
                            data_quality_notes = COALESCE(data_quality_notes, '') || 
                                ' | AI common name update (' || ? || '): ' || datetime('now')
                        WHERE cluster_id = ?
                    ''', (new_common_name, confidence, defn["cluster_id"]))
                    
                    if cur.rowcount > 0:
                        updated += 1
                        LOGGER.info(f"Updated {defn['derived_term']}: {dup['common_name']} → {new_common_name}")
                
                processed += 1
                time.sleep(0.5)
                
            except Exception as e:
                LOGGER.error(f"Error processing {defn['derived_term']}: {e}")
                processed += 1
    
    conn.commit()
    conn.close()
    
    LOGGER.info(f"Processed {processed}, updated {updated} common names")
    return updated


def show_stats():
    """Show statistics about duplicate common names."""
    duplicates = find_duplicate_common_names()
    
    print(f"\n=== Common Name Duplicate Statistics ===\n")
    print(f"Total common names with duplicates: {len(duplicates)}")
    
    total_affected = sum(d["definition_count"] for d in duplicates)
    print(f"Total definitions affected: {total_affected}")
    
    print(f"\nTop 20 duplicates:")
    print(f"{'Common Name':<35} | Definitions")
    print("-" * 50)
    
    for dup in duplicates[:20]:
        print(f"{dup['common_name']:<35} | {dup['definition_count']}")


def main():
    parser = argparse.ArgumentParser(description="AI Worker for Common Name Research")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    stats_parser = subparsers.add_parser("stats", help="Show duplicate statistics")
    
    export_parser = subparsers.add_parser("export", help="Export to JSONL for batch")
    export_parser.add_argument("--limit", type=int, default=100, help="Max items to export")
    
    export_all_parser = subparsers.add_parser("export-all", help="Export ALL items in batches of 500")
    export_all_parser.add_argument("--batch-size", type=int, default=500, help="Items per batch file")
    
    submit_parser = subparsers.add_parser("submit", help="Submit batch to OpenAI")
    submit_parser.add_argument("--file", required=True, help="JSONL file path")
    
    submit_all_parser = subparsers.add_parser("submit-all", help="Submit all common_name_export files")
    
    status_parser = subparsers.add_parser("status", help="Check batch status")
    status_parser.add_argument("--batch-id", required=True, help="Batch ID")
    
    import_parser = subparsers.add_parser("import", help="Import batch results")
    import_parser.add_argument("--batch-id", required=True, help="Batch ID")
    
    process_parser = subparsers.add_parser("process", help="Process directly (non-batch)")
    process_parser.add_argument("--limit", type=int, default=10, help="Max items to process")
    
    args = parser.parse_args()
    
    if args.command == "stats":
        show_stats()
    elif args.command == "export":
        export_batch(args.limit)
    elif args.command == "export-all":
        export_all_batches(args.batch_size)
    elif args.command == "submit":
        submit_batch(args.file)
    elif args.command == "submit-all":
        submit_all_batches()
    elif args.command == "status":
        check_status(args.batch_id)
    elif args.command == "import":
        import_results(args.batch_id)
    elif args.command == "process":
        process_direct(args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
