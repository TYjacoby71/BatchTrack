"""Stage 3 runner: enumeration (post-compilation).

This is the ONLY stage allowed to propose NEW items/variations for an ingredient after Stage 2 compilation.

Workflow (Stage 3):
- select compiled ingredients (ingredients.compiled_at is set)
- skip those with ingredients.enumeration_status == 'done'
- ask AI to propose additional item identities (variation + physical_form + bypass flags)
- ask AI to complete schemas for those new items
- upsert by re-saving the compiled payload through database_manager.upsert_compiled_ingredient()
- mark enumeration_status done/error
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func

from . import ai_worker, database_manager

LOGGER = logging.getLogger(__name__)

SLEEP_SECONDS = float(os.getenv("ENUMERATION_SLEEP_SECONDS", "2.0"))
MAX_ATTEMPTS = int(os.getenv("ENUMERATION_MAX_ATTEMPTS", "2"))


ENUM_SCHEMA = r"""
Return JSON using this schema (all strings trimmed; lists sorted alphabetically):
{
  "new_items": [
    {
      "variation": "string",
      "physical_form": "one of the curated Physical Forms enum",
      "form_bypass": true | false,
      "variation_bypass": true | false
    }
  ]
}
"""


def _clean_json(text: str) -> dict[str, Any]:
    try:
        blob = json.loads(text or "{}")
        return blob if isinstance(blob, dict) else {}
    except Exception:
        return {}


def _select_next_terms(limit: int | None) -> list[str]:
    database_manager.ensure_tables_exist()
    terms: list[str] = []
    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.IngredientRecord.term, database_manager.IngredientRecord.priority)
            .filter(database_manager.IngredientRecord.compiled_at.isnot(None))
            .filter(
                (database_manager.IngredientRecord.enumeration_status.is_(None))
                | (database_manager.IngredientRecord.enumeration_status != "done")
            )
            .order_by(
                func.coalesce(database_manager.IngredientRecord.priority, 0).desc(),
                database_manager.IngredientRecord.compiled_at.desc(),
                database_manager.IngredientRecord.term.asc(),
            )
        )
        if limit:
            q = q.limit(int(limit))
        for (t, _) in q.all():
            terms.append(str(t))
    return terms


def _build_new_item_stubs(new_items: list[dict]) -> list[dict]:
    stubs: list[dict] = []
    for it in new_items:
        if not isinstance(it, dict):
            continue
        stubs.append(
            {
                "variation": (it.get("variation") or "").strip(),
                "physical_form": (it.get("physical_form") or "").strip(),
                "form_bypass": bool(it.get("form_bypass", False)),
                "variation_bypass": bool(it.get("variation_bypass", False)),
                "synonyms": [],
                "applications": [],
                "function_tags": [],
                "safety_tags": [],
                "sds_hazards": [],
                "storage": {},
                "specifications": {},
                "sourcing": {},
            }
        )
    return stubs


def enumerate_term(term: str) -> bool:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        ing = session.get(database_manager.IngredientRecord, term)
        if ing is None:
            return False
        if (ing.enumeration_status or "").strip().lower() == "done":
            return True
        ing.enumeration_status = "processing"
        ing.enumeration_attempts = int(getattr(ing, "enumeration_attempts", 0) or 0) + 1
        ing.enumeration_error = None
        compiled_payload = _clean_json(getattr(ing, "payload_json", "{}"))

    base = database_manager.get_normalized_term(term) or {}
    ingredient = compiled_payload.get("ingredient") if isinstance(compiled_payload.get("ingredient"), dict) else {}
    existing_items = ingredient.get("items") if isinstance(ingredient.get("items"), list) else []

    # Ask AI for new item identities only.
    prompt = f"""
You are Stage 3 (Enumeration — Items). Propose NEW missing purchasable item identities for ingredient: "{term}".

Rules:
- Only propose items that are NOT already present.
- Do NOT modify existing items.
- Keep variations realistic for small batch makers.

Existing items (do not duplicate):
{json.dumps(existing_items, ensure_ascii=False, indent=2, sort_keys=True)[:12000]}

SCHEMA:
{ENUM_SCHEMA}
"""

    # Use ai_worker as a generic JSON caller (single prompt mode).
    # We rely on the same OpenAI settings/env as compiler.
    client = ai_worker.openai.OpenAI(api_key=ai_worker.openai.api_key)  # type: ignore[attr-defined]
    try:
        enum_payload = ai_worker._call_openai_json(client, ai_worker.SYSTEM_PROMPT, prompt)  # type: ignore[attr-defined]
        new_items = enum_payload.get("new_items") if isinstance(enum_payload.get("new_items"), list) else []
    except Exception as exc:  # pylint: disable=broad-except
        with database_manager.get_session() as session:
            ing2 = session.get(database_manager.IngredientRecord, term)
            if ing2 is not None:
                ing2.enumeration_status = "error"
                ing2.enumeration_error = str(exc)
        return False

    # Nothing new -> mark done.
    if not new_items:
        with database_manager.get_session() as session:
            ing2 = session.get(database_manager.IngredientRecord, term)
            if ing2 is not None:
                ing2.enumeration_status = "done"
                ing2.enumerated_at = datetime.now(timezone.utc)
        return True

    # Complete schemas for those new items (reuse ai_worker completion mode).
    stubs = _build_new_item_stubs(new_items)
    try:
        ingredient_core = dict(ingredient)
        ingredient_core.pop("items", None)
        completed_new = ai_worker.complete_item_stubs(term, ingredient_core=ingredient_core, base_context=base, item_stubs=stubs)
        # Mark provenance so DB can distinguish compiled vs enumerated items.
        for it in completed_new:
            if isinstance(it, dict):
                it["item_source"] = "enumerator"
                it["source_stage"] = "enumerator"
        ingredient["items"] = list(existing_items) + list(completed_new)
        compiled_payload["ingredient"] = ingredient

        labels: list[str] = []
        for it in completed_new:
            if not isinstance(it, dict):
                continue
            v = (it.get("variation") or "").strip()
            f = (it.get("physical_form") or "").strip()
            labels.append(f"{v} [{f}]".strip() if v else f"[{f}]")
        # Re-save through DB writer.
        database_manager.upsert_compiled_ingredient(term, compiled_payload, seed_category=base.get("seed_category"))
        with database_manager.get_session() as session:
            ing3 = session.get(database_manager.IngredientRecord, term)
            if ing3 is not None:
                ing3.enumeration_status = "done"
                ing3.enumerated_at = datetime.now(timezone.utc)
                ing3.enumeration_notes = f"added_items={len(completed_new)}; new={', '.join(labels[:12])}"
        # Human-readable log summary.
        if completed_new:
            LOGGER.info("Stage 3 enumeration complete for %s: added_items=%s (%s)", term, len(completed_new), ", ".join(labels[:12]))
        return True
    except Exception as exc:  # pylint: disable=broad-except
        with database_manager.get_session() as session:
            ing3 = session.get(database_manager.IngredientRecord, term)
            if ing3 is not None:
                ing3.enumeration_status = "error"
                ing3.enumeration_error = str(exc)
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run enumeration over compiled ingredients")
    p.add_argument("--limit", type=int, default=int(os.getenv("ENUMERATION_LIMIT", "50")))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=os.getenv("COMPILER_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv or sys.argv[1:])
    terms = _select_next_terms(int(args.limit) if int(args.limit or 0) > 0 else None)
    if not terms:
        LOGGER.info("No completed terms to enumerate.")
        return
    ok = 0
    for term in terms:
        if enumerate_term(term):
            ok += 1
        time.sleep(SLEEP_SECONDS)
    LOGGER.info("Enumeration finished: ok=%s total=%s", ok, len(terms))


if __name__ == "__main__":
    main()

