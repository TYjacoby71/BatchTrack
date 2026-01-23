"""OpenAI Batch API service for cost-effective bulk ingredient compilation.

This module provides export/import functionality for OpenAI's Batch API,
enabling 50% cost savings on large-scale ingredient processing.

Usage:
    # Export Stage 1 pending terms to JSONL
    python -m data_builder.ingredients.openai_batch_service export --stage 1 --limit 50

    # Export Stage 2 pending items to JSONL  
    python -m data_builder.ingredients.openai_batch_service export --stage 2 --limit 50

    # Submit batch to OpenAI
    python -m data_builder.ingredients.openai_batch_service submit --file exports/batch_stage1_xxx.jsonl

    # Check batch status
    python -m data_builder.ingredients.openai_batch_service status --batch-id batch_xxx

    # Import completed batch results
    python -m data_builder.ingredients.openai_batch_service import --batch-id batch_xxx
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import openai

from . import database_manager
from .ai_worker import (
    MODEL_NAME,
    SYSTEM_PROMPT,
    TEMPERATURE,
    _render_cluster_term_prompt,
    _render_items_prompt,
    _render_items_completion_prompt,
    _ensure_item_fields,
)
from .compiler import _extract_stage1_field, _build_cluster_context

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

openai.api_key = os.environ.get("OPENAI_API_KEY")


def _get_stage1_pending_clusters(limit: int | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Get Stage 1 pending clusters with their context."""
    database_manager.ensure_tables_exist()
    
    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceDefinition.cluster_id).outerjoin(
            database_manager.CompiledClusterRecord,
            database_manager.CompiledClusterRecord.cluster_id == database_manager.SourceDefinition.cluster_id,
        )
        q = q.filter(database_manager.SourceDefinition.cluster_id.isnot(None))
        q = q.filter(
            (database_manager.CompiledClusterRecord.cluster_id.is_(None))
            | (database_manager.CompiledClusterRecord.term_status.notin_(["done", "batch_pending"]))
        )
        q = q.order_by(database_manager.SourceDefinition.cluster_id.asc())
        ids = [str(r[0]) for r in q.all() if r and r[0]]
    
    if not ids:
        return []
    
    priority_map = database_manager.build_cluster_priority_map()
    ids.sort(key=lambda cid: (-int(priority_map.get(cid, database_manager.DEFAULT_PRIORITY)), cid))
    
    if limit:
        ids = ids[:int(limit)]
    
    results = []
    for cid in ids:
        context = _build_cluster_context(cid)
        results.append((cid, context))
    
    return results


def _get_stage2_pending_clusters(limit: int | None = None) -> list[tuple[str, str, dict[str, Any], dict[str, Any], bool]]:
    """Get Stage 2 pending clusters with their context.
    
    Returns list of (cluster_id, term, ingredient_core, base_context, has_seed_items)
    
    Optimized to use raw SQL for speed.
    """
    database_manager.ensure_tables_exist()
    
    from sqlalchemy import text
    
    # Use raw SQL for optimal performance
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    sql = text(f"""
        SELECT cc.cluster_id, cc.compiled_term, cc.origin, cc.ingredient_category,
               cc.refinement_level, cc.derived_from, cc.botanical_name, cc.inci_name, 
               cc.cas_number, cc.priority
        FROM compiled_clusters cc
        WHERE cc.term_status = 'done'
        AND EXISTS (
            SELECT 1 FROM compiled_cluster_items cci 
            WHERE cci.cluster_id = cc.cluster_id 
            AND cci.item_status NOT IN ('done', 'batch_pending')
        )
        ORDER BY COALESCE(cc.priority, {database_manager.DEFAULT_PRIORITY}) DESC, cc.cluster_id
        {limit_clause}
    """)
    
    with database_manager.get_session() as session:
        result = session.execute(sql)
        rows = result.fetchall()
    
    if not rows:
        return []
    
    # Collect cluster_ids for batch item fetch
    cluster_ids = [str(row[0]) for row in rows]
    
    # Batch fetch all items for these clusters in ONE query
    with database_manager.get_session() as session:
        all_items = (
            session.query(database_manager.CompiledClusterItemRecord)
            .filter(database_manager.CompiledClusterItemRecord.cluster_id.in_(cluster_ids))
            .filter(database_manager.CompiledClusterItemRecord.item_status.notin_(["done", "batch_pending"]))
            .all()
        )
    
    # Group items by cluster_id
    items_by_cluster: dict[str, list] = {}
    for item in all_items:
        cid = str(item.cluster_id)
        if cid not in items_by_cluster:
            items_by_cluster[cid] = []
        items_by_cluster[cid].append({
            "variation": item.derived_variation or "",
            "physical_form": item.derived_physical_form or "",
        })
    
    # Build results
    results = []
    for row in rows:
        cid = str(row[0])
        term = row[1] or ""
        
        ingredient_core = {
            "origin": row[2],
            "ingredient_category": row[3],
            "refinement_level": row[4],
            "derived_from": row[5],
            "botanical_name": row[6],
            "inci_name": row[7],
            "cas_number": row[8],
        }
        
        seed_items = items_by_cluster.get(cid, [])
        base_context = {"seed_items": seed_items} if seed_items else {}
        has_seed_items = bool(seed_items)
        
        results.append((cid, term, ingredient_core, base_context, has_seed_items))
    
    return results


def export_stage1_batch(limit: int | None = None) -> Path:
    """Export Stage 1 pending clusters to JSONL for OpenAI Batch API."""
    clusters = _get_stage1_pending_clusters(limit=limit)
    
    if not clusters:
        LOGGER.info("No Stage 1 pending clusters to export")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_stage1_{timestamp}.jsonl"
    filepath = EXPORTS_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        for cid, context in clusters:
            prompt = _render_cluster_term_prompt(cid, context)
            request = {
                "custom_id": f"stage1_{cid}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL_NAME,
                    "temperature": TEMPERATURE,
                    "max_tokens": 4096,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
            }
            f.write(json.dumps(request, ensure_ascii=False) + "\n")
    
    file_size_kb = filepath.stat().st_size / 1024
    LOGGER.info(f"Exported {len(clusters)} Stage 1 clusters to {filepath} ({file_size_kb:.1f} KB)")
    
    # Mark exported clusters as batch_pending so real-time compiler skips them
    _mark_clusters_batch_pending([cid for cid, _ in clusters], stage=1)
    
    return filepath


def _mark_clusters_batch_pending(cluster_ids: list[str], stage: int) -> None:
    """Mark clusters as batch_pending to prevent real-time compiler from processing them."""
    with database_manager.get_session() as session:
        for cid in cluster_ids:
            if stage == 1:
                # Check if record exists, create minimal one if not
                rec = session.query(database_manager.CompiledClusterRecord).filter_by(cluster_id=cid).first()
                if rec:
                    rec.term_status = "batch_pending"
                else:
                    new_rec = database_manager.CompiledClusterRecord(
                        cluster_id=cid,
                        term_status="batch_pending",
                        priority=50
                    )
                    session.add(new_rec)
            elif stage == 2:
                # For stage 2, update item_status on items
                items = session.query(database_manager.CompiledClusterItemRecord).filter_by(cluster_id=cid).all()
                for item in items:
                    if item.item_status != "done":
                        item.item_status = "batch_pending"
        session.commit()
    LOGGER.info(f"Marked {len(cluster_ids)} clusters as batch_pending for Stage {stage}")


def export_stage2_batch(limit: int | None = None) -> Path:
    """Export Stage 2 pending clusters to JSONL for OpenAI Batch API."""
    clusters = _get_stage2_pending_clusters(limit=limit)
    
    if not clusters:
        LOGGER.info("No Stage 2 pending clusters to export")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_stage2_{timestamp}.jsonl"
    filepath = EXPORTS_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        for cid, term, ingredient_core, base_context, has_seed_items in clusters:
            if has_seed_items:
                prompt = _render_items_completion_prompt(term, ingredient_core, base_context)
            else:
                prompt = _render_items_prompt(term, ingredient_core, base_context)
            request = {
                "custom_id": f"stage2_{cid}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL_NAME,
                    "temperature": TEMPERATURE,
                    "max_tokens": 4096,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
            }
            f.write(json.dumps(request, ensure_ascii=False) + "\n")
    
    file_size_kb = filepath.stat().st_size / 1024
    LOGGER.info(f"Exported {len(clusters)} Stage 2 clusters to {filepath} ({file_size_kb:.1f} KB)")
    
    # Mark exported clusters as batch_pending so real-time compiler skips them
    _mark_clusters_batch_pending([cid for cid, _, _, _, _ in clusters], stage=2)
    
    return filepath


def submit_batch(filepath: str | Path) -> str:
    """Submit a JSONL batch file to OpenAI and return the batch ID."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Batch file not found: {filepath}")
    
    client = openai.OpenAI(api_key=openai.api_key)
    
    LOGGER.info(f"Uploading batch file: {filepath}")
    with open(filepath, "rb") as f:
        batch_input_file = client.files.create(file=f, purpose="batch")
    
    LOGGER.info(f"File uploaded with ID: {batch_input_file.id}")
    
    batch = client.batches.create(
        input_file_id=batch_input_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"source": "ingredient_compiler", "file": filepath.name},
    )
    
    LOGGER.info(f"Batch created with ID: {batch.id}")
    LOGGER.info(f"Status: {batch.status}")
    
    batch_info = {
        "batch_id": batch.id,
        "input_file_id": batch_input_file.id,
        "status": batch.status,
        "source_file": str(filepath),
        "created_at": datetime.now().isoformat(),
    }
    info_file = EXPORTS_DIR / f"{batch.id}_info.json"
    with open(info_file, "w") as f:
        json.dump(batch_info, f, indent=2)
    
    return batch.id


def check_batch_status(batch_id: str) -> dict[str, Any]:
    """Check the status of a batch job."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    
    client = openai.OpenAI(api_key=openai.api_key)
    batch = client.batches.retrieve(batch_id)
    
    status_info = {
        "batch_id": batch.id,
        "status": batch.status,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "failed_at": batch.failed_at,
        "request_counts": {
            "total": batch.request_counts.total if batch.request_counts else 0,
            "completed": batch.request_counts.completed if batch.request_counts else 0,
            "failed": batch.request_counts.failed if batch.request_counts else 0,
        },
        "output_file_id": batch.output_file_id,
        "error_file_id": batch.error_file_id,
    }
    
    LOGGER.info(f"Batch {batch_id}: {batch.status}")
    if batch.request_counts:
        LOGGER.info(f"  Completed: {batch.request_counts.completed}/{batch.request_counts.total}")
        if batch.request_counts.failed > 0:
            LOGGER.warning(f"  Failed: {batch.request_counts.failed}")
    
    return status_info


def download_batch_results(batch_id: str) -> Path | None:
    """Download the results of a completed batch."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    
    client = openai.OpenAI(api_key=openai.api_key)
    batch = client.batches.retrieve(batch_id)
    
    if batch.status != "completed":
        LOGGER.warning(f"Batch {batch_id} is not completed yet (status: {batch.status})")
        return None
    
    if not batch.output_file_id:
        LOGGER.error(f"Batch {batch_id} has no output file")
        return None
    
    content = client.files.content(batch.output_file_id)
    output_path = EXPORTS_DIR / f"{batch_id}_results.jsonl"
    
    with open(output_path, "wb") as f:
        f.write(content.read())
    
    LOGGER.info(f"Downloaded results to: {output_path}")
    return output_path


def import_stage1_results(results_path: str | Path) -> dict[str, int]:
    """Import Stage 1 batch results into the database."""
    results_path = Path(results_path)
    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")
    
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                result = json.loads(line)
                custom_id = result.get("custom_id", "")
                
                if not custom_id.startswith("stage1_"):
                    stats["skipped"] += 1
                    continue
                
                cluster_id = custom_id.replace("stage1_", "")
                
                response = result.get("response", {})
                if response.get("status_code") != 200:
                    LOGGER.error(f"Request failed for {cluster_id}: {response}")
                    stats["failed"] += 1
                    continue
                
                body = response.get("body", {})
                choices = body.get("choices", [])
                if not choices:
                    LOGGER.error(f"No choices in response for {cluster_id}")
                    stats["failed"] += 1
                    continue
                
                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    LOGGER.error(f"Empty content for {cluster_id}")
                    stats["failed"] += 1
                    continue
                
                payload = json.loads(content)
                
                _apply_stage1_result(cluster_id, payload)
                stats["success"] += 1
                LOGGER.info(f"Imported Stage 1 result for {cluster_id}")
                
            except Exception as e:
                LOGGER.exception(f"Error processing result: {e}")
                stats["failed"] += 1
    
    LOGGER.info(f"Stage 1 import complete: {stats}")
    return stats


def _apply_stage1_result(cluster_id: str, payload: dict[str, Any]) -> None:
    """Apply a Stage 1 AI result to the database (matches compiler.py behavior)."""
    from datetime import timezone
    from .compiler import _mirror_cluster_into_compiled
    
    _mirror_cluster_into_compiled(cluster_id)
    
    term = payload.get("term") or ""
    common_name = payload.get("common_name") or ""
    priority = payload.get("maker_priority")
    core = payload.get("ingredient_core", {})
    dq = payload.get("data_quality", {})
    
    if priority is not None:
        priority = max(1, min(100, int(priority)))
    
    with database_manager.get_session() as session:
        rec = session.query(database_manager.CompiledClusterRecord).filter_by(cluster_id=cluster_id).first()
        if not rec:
            rec = database_manager.CompiledClusterRecord(cluster_id=cluster_id)
            session.add(rec)
        
        rec.compiled_term = term
        rec.term_status = "done"
        rec.priority = priority
        
        rec.origin = _extract_stage1_field(core.get("origin"))
        rec.ingredient_category = _extract_stage1_field(core.get("ingredient_category"))
        rec.refinement_level = _extract_stage1_field(core.get("base_refinement")) or _extract_stage1_field(core.get("refinement_level"))
        rec.derived_from = _extract_stage1_field(core.get("derived_from"))
        rec.botanical_name = _extract_stage1_field(core.get("botanical_name"))
        rec.inci_name = _extract_stage1_field(core.get("inci_name"))
        rec.cas_number = _extract_stage1_field(core.get("cas_number"))
        
        # Store common_name and data quality in columns (no JSON blobs)
        rec.common_name = common_name
        
        # Extract confidence from data_quality if present
        if isinstance(dq, dict):
            confidence = dq.get("confidence")
            if confidence is not None:
                try:
                    rec.confidence_score = int(confidence)
                except (TypeError, ValueError):
                    pass
            caveats = dq.get("caveats", [])
            if caveats:
                rec.data_quality_notes = "; ".join(str(c) for c in caveats) if isinstance(caveats, list) else str(caveats)
        
        session.commit()


def import_stage2_results(results_path: str | Path) -> dict[str, int]:
    """Import Stage 2 batch results into the database."""
    results_path = Path(results_path)
    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")
    
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                result = json.loads(line)
                custom_id = result.get("custom_id", "")
                
                if not custom_id.startswith("stage2_"):
                    stats["skipped"] += 1
                    continue
                
                cluster_id = custom_id.replace("stage2_", "")
                
                response = result.get("response", {})
                if response.get("status_code") != 200:
                    LOGGER.error(f"Request failed for {cluster_id}: {response}")
                    stats["failed"] += 1
                    continue
                
                body = response.get("body", {})
                choices = body.get("choices", [])
                if not choices:
                    LOGGER.error(f"No choices in response for {cluster_id}")
                    stats["failed"] += 1
                    continue
                
                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    LOGGER.error(f"Empty content for {cluster_id}")
                    stats["failed"] += 1
                    continue
                
                payload = json.loads(content)
                
                _apply_stage2_result(cluster_id, payload)
                stats["success"] += 1
                LOGGER.info(f"Imported Stage 2 result for {cluster_id}")
                
            except Exception as e:
                LOGGER.exception(f"Error processing result: {e}")
                stats["failed"] += 1
    
    LOGGER.info(f"Stage 2 import complete: {stats}")
    return stats


def _apply_stage2_result(cluster_id: str, payload: dict[str, Any]) -> None:
    """Apply a Stage 2 AI result to the database (matches compiler.py behavior)."""
    from datetime import timezone
    
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    
    items = [_ensure_item_fields(it) for it in items if isinstance(it, dict)]
    
    with database_manager.get_session() as session:
        existing_items = session.query(database_manager.CompiledClusterItemRecord).filter_by(cluster_id=cluster_id).all()
        now = datetime.now(timezone.utc)
        
        for ai_item in items:
            variation = ai_item.get("variation", {})
            if isinstance(variation, dict):
                variation = variation.get("value", "")
            variation = variation or ""
            
            physical_form = ai_item.get("physical_form", {})
            if isinstance(physical_form, dict):
                physical_form = physical_form.get("value", "")
            physical_form = physical_form or ""
            
            matched_item = None
            for item in existing_items:
                if (item.derived_variation or "") == variation and (item.derived_physical_form or "") == physical_form:
                    matched_item = item
                    break
            
            if matched_item:
                matched_item.item_json = json.dumps(ai_item, ensure_ascii=False, sort_keys=True)
                matched_item.item_status = "done"
                matched_item.item_compiled_at = now
                matched_item.item_error = None
                matched_item.updated_at = now
                
                matched_item.master_category = ai_item.get("master_category", "")
                matched_item.description = ai_item.get("description", "")
                matched_item.color = ai_item.get("color", "")
                matched_item.odor_profile = ai_item.get("odor_profile", "")
                matched_item.flavor_profile = ai_item.get("flavor_profile", "")
                
                processing_method = ai_item.get("processing_method", {})
                if isinstance(processing_method, dict):
                    matched_item.processing_method = processing_method.get("value", "")
                else:
                    matched_item.processing_method = processing_method or ""
        
        session.commit()
    
    from .compiler import _finalize_cluster_if_complete
    _finalize_cluster_if_complete(cluster_id)


def main():
    parser = argparse.ArgumentParser(description="OpenAI Batch API service for ingredient compilation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    export_parser = subparsers.add_parser("export", help="Export pending terms to JSONL")
    export_parser.add_argument("--stage", type=int, required=True, choices=[1, 2], help="Stage to export (1 or 2)")
    export_parser.add_argument("--limit", type=int, default=None, help="Max clusters to export")
    
    submit_parser = subparsers.add_parser("submit", help="Submit batch to OpenAI")
    submit_parser.add_argument("--file", type=str, required=True, help="JSONL file to submit")
    
    status_parser = subparsers.add_parser("status", help="Check batch status")
    status_parser.add_argument("--batch-id", type=str, required=True, help="Batch ID to check")
    
    import_parser = subparsers.add_parser("import", help="Import completed batch results")
    import_parser.add_argument("--batch-id", type=str, help="Batch ID to download and import")
    import_parser.add_argument("--file", type=str, help="Local results file to import (if already downloaded)")
    import_parser.add_argument("--stage", type=int, required=True, choices=[1, 2], help="Stage of the batch (1 or 2)")
    
    download_parser = subparsers.add_parser("download", help="Download batch results without importing")
    download_parser.add_argument("--batch-id", type=str, required=True, help="Batch ID to download")
    
    args = parser.parse_args()
    
    if args.command == "export":
        if args.stage == 1:
            result = export_stage1_batch(limit=args.limit)
        else:
            result = export_stage2_batch(limit=args.limit)
        if result:
            print(f"Exported to: {result}")
        else:
            print("Nothing to export")
    
    elif args.command == "submit":
        batch_id = submit_batch(args.file)
        print(f"Batch submitted: {batch_id}")
        print(f"Check status with: python -m data_builder.ingredients.openai_batch_service status --batch-id {batch_id}")
    
    elif args.command == "status":
        status = check_batch_status(args.batch_id)
        print(json.dumps(status, indent=2, default=str))
    
    elif args.command == "download":
        result = download_batch_results(args.batch_id)
        if result:
            print(f"Downloaded to: {result}")
        else:
            print("Batch not ready or no output file")
    
    elif args.command == "import":
        if args.file:
            results_path = Path(args.file)
        elif args.batch_id:
            results_path = download_batch_results(args.batch_id)
            if not results_path:
                print("Failed to download batch results")
                sys.exit(1)
        else:
            print("Either --batch-id or --file is required")
            sys.exit(1)
        
        if args.stage == 1:
            stats = import_stage1_results(results_path)
        else:
            stats = import_stage2_results(results_path)
        print(f"Import complete: {stats}")


if __name__ == "__main__":
    main()
