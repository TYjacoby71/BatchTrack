"""Lightweight viewer/exporter for the ingredient state DB.

This is intentionally small and self-contained: it reads `Final DB.db`
and renders a basic table + CSV export so you can *see* progress and back it up.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from flask import Flask, Response, request, send_file
from flask import redirect
from markupsafe import escape

from . import database_manager


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool_compiled(status: str) -> bool:
    return (status or "").lower() == "completed"


def _serialize_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _safe_pretty_json(raw: Any) -> str:
    """Pretty-print JSON for UI display (never raises)."""
    try:
        if raw is None:
            return ""
        if isinstance(raw, (dict, list)):
            return json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return ""
            parsed = json.loads(text)
            return json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)
        return json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(raw or "")

def _url_path(value: str) -> str:
    """URL-escape a value intended for a path segment."""
    return urllib.parse.quote(str(value or ""), safe="")


def _url_qs(value: str) -> str:
    """URL-escape a value intended for querystring value."""
    return urllib.parse.quote_plus(str(value or ""))


def create_app(db_path: Optional[Path] = None) -> Flask:
    app = Flask(__name__)

    # Ensure DB exists / schema present.
    if db_path is not None:
        # NOTE: database_manager reads FINAL_DB_PATH at import-time by default.
        # Use configure_db_path so --db-path reliably takes effect.
        database_manager.configure_db_path(str(db_path))
    database_manager.ensure_tables_exist()

    @app.get("/")
    def index() -> str:
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().lower()
        show_quarantine = (request.args.get("show_quarantine") or "").strip().lower() in {"1", "true", "yes", "y", "on"}
        min_priority = _parse_int(request.args.get("min_priority"), 1)
        max_priority = _parse_int(request.args.get("max_priority"), 10)
        page = max(1, _parse_int(request.args.get("page"), 1))
        page_size = min(500, max(10, _parse_int(request.args.get("page_size"), 50)))
        offset = (page - 1) * page_size

        database_manager.ensure_tables_exist()

        with database_manager.get_session() as session:
            base = session.query(database_manager.TaskQueue)
            if q:
                base = base.filter(database_manager.TaskQueue.term.ilike(f"%{q}%"))
            if status:
                base = base.filter(database_manager.TaskQueue.status == status)
            base = base.filter(database_manager.TaskQueue.priority >= min_priority)
            base = base.filter(database_manager.TaskQueue.priority <= max_priority)

            total = base.count()
            rows = (
                base.order_by(database_manager.TaskQueue.term.asc())
                .offset(offset)
                .limit(page_size)
                .all()
            )

            page_terms = [r.term for r in rows]
            ingredient_rows = (
                session.query(database_manager.IngredientRecord)
                .filter(database_manager.IngredientRecord.term.in_(page_terms))
                .all()
            )
            ingredients_by_term = {r.term: r for r in ingredient_rows}
            # Fetch all items and filter at render time so we can show "hidden quarantine"
            # counts instead of making it look like items are missing.
            all_item_rows = (
                session.query(database_manager.IngredientItemRecord)
                .filter(database_manager.IngredientItemRecord.ingredient_term.in_(page_terms))
                .order_by(database_manager.IngredientItemRecord.ingredient_term.asc(), database_manager.IngredientItemRecord.item_name.asc())
                .all()
            )
            items_all_by_term: dict[str, list[database_manager.IngredientItemRecord]] = {}
            for item in all_item_rows:
                items_all_by_term.setdefault(item.ingredient_term, []).append(item)

            item_rows = [
                i
                for i in all_item_rows
                if (show_quarantine or (getattr(i, "status", "") or "").strip().lower() == "active")
            ]

            # Pull normalized list attributes for displayed items (applications, function_tags, etc.)
            item_ids = [i.id for i in item_rows if getattr(i, "id", None) is not None]
            value_rows = []
            if item_ids:
                value_rows = (
                    session.query(database_manager.IngredientItemValue)
                    .filter(database_manager.IngredientItemValue.item_id.in_(item_ids))
                    .order_by(
                        database_manager.IngredientItemValue.item_id.asc(),
                        database_manager.IngredientItemValue.field.asc(),
                        database_manager.IngredientItemValue.value.asc(),
                    )
                    .all()
                )
            values_by_item: dict[int, dict[str, list[str]]] = {}
            for vr in value_rows:
                values_by_item.setdefault(vr.item_id, {}).setdefault(vr.field, []).append(vr.value)

            # Summary counts
            summary = database_manager.get_queue_summary()
            source_summary = database_manager.get_source_item_summary()

        def _qs(**overrides: Any) -> str:
            args = dict(request.args)
            for k, v in overrides.items():
                if v is None:
                    args.pop(k, None)
                else:
                    args[k] = str(v)
            # stable ordering not required
            parts = [f"{k}={args[k]}" for k in args]
            return "?" + "&".join(parts) if parts else ""

        def _render_item_block(i: database_manager.IngredientItemRecord) -> str:
            scalars = [
                ("status", getattr(i, "status", "") or ""),
                ("approved", "true" if bool(getattr(i, "approved", False)) else "false"),
                ("needs_review_reason", getattr(i, "needs_review_reason", "") or ""),
                ("shelf_life_days", getattr(i, "shelf_life_days", None)),
                ("ph_min", getattr(i, "ph_min", None)),
                ("ph_max", getattr(i, "ph_max", None)),
                ("flash_point_c", getattr(i, "flash_point_c", None)),
                ("melting_point_c_min", getattr(i, "melting_point_c_min", None)),
                ("melting_point_c_max", getattr(i, "melting_point_c_max", None)),
                ("sap_naoh", getattr(i, "sap_naoh", None)),
                ("sap_koh", getattr(i, "sap_koh", None)),
                ("iodine_value", getattr(i, "iodine_value", None)),
                ("usage_leave_on_max", getattr(i, "usage_leave_on_max", None)),
                ("usage_rinse_off_max", getattr(i, "usage_rinse_off_max", None)),
                ("storage_temp_c_min", getattr(i, "storage_temp_c_min", None)),
                ("storage_temp_c_max", getattr(i, "storage_temp_c_max", None)),
                ("storage_humidity_max", getattr(i, "storage_humidity_max", None)),
            ]
            scalars = [(k, v) for k, v in scalars if v not in (None, "", "None")]
            scalar_html = "".join(
                f"<div class='muted'><b>{escape(k)}</b>: {escape(str(v))}</div>" for k, v in scalars
            )

            tags = values_by_item.get(int(i.id), {}) if getattr(i, "id", None) is not None else {}
            tag_html = ""
            if tags:
                sections = []
                for field, values in tags.items():
                    if not values:
                        continue
                    preview = ", ".join([escape(v) for v in values[:16]])
                    suffix = f" … (+{len(values) - 16})" if len(values) > 16 else ""
                    sections.append(f"<div class='muted'><b>{escape(field)}</b>: {preview}{suffix}</div>")
                tag_html = "".join(sections)

            pretty = _safe_pretty_json(getattr(i, "item_json", "") or "")
            json_html = (
                "<div style='margin-top:8px;'><b>item_json</b></div>"
                "<pre style='white-space:pre-wrap; font-size:12px; background:#fafafa; border:1px solid #eee; padding:10px; border-radius:8px;'>"
                f"{escape(pretty)}"
                "</pre>"
                if pretty
                else "<div class='muted' style='margin-top:8px;'>No item_json</div>"
            )

            return (
                "<details style='margin-top:6px;'>"
                f"<summary><b>{escape(i.item_name)}</b> "
                f"<span class='muted'>(variation: {escape(i.variation or '')}, form: {escape(i.physical_form or '')})</span>"
                "</summary>"
                f"<div style='margin-top:8px;'>{scalar_html}{tag_html}{json_html}</div>"
                "</details>"
            )

        def _render_term_cell(term: str) -> str:
            ingredient = ingredients_by_term.get(term)
            all_items = items_all_by_term.get(term, [])
            if show_quarantine:
                items = all_items
            else:
                items = [i for i in all_items if (getattr(i, "status", "") or "").strip().lower() == "active"]
            if not ingredient and not items:
                return term
            core_bits = []
            if ingredient:
                if getattr(ingredient, "ingredient_category", None):
                    core_bits.append(f"<div class='muted'><b>ingredient_category</b>: {ingredient.ingredient_category}</div>")
                if getattr(ingredient, "origin", None):
                    core_bits.append(f"<div class='muted'><b>origin</b>: {ingredient.origin}</div>")
                if getattr(ingredient, "refinement_level", None):
                    core_bits.append(f"<div class='muted'><b>refinement</b>: {ingredient.refinement_level}</div>")
                if getattr(ingredient, "derived_from", None):
                    core_bits.append(f"<div class='muted'><b>derived_from</b>: {ingredient.derived_from}</div>")
                if ingredient.category:
                    core_bits.append(f"<div class='muted'><b>category</b>: {ingredient.category}</div>")
                if ingredient.botanical_name:
                    core_bits.append(f"<div class='muted'><b>botanical</b>: {ingredient.botanical_name}</div>")
                if ingredient.inci_name:
                    core_bits.append(f"<div class='muted'><b>inci</b>: {ingredient.inci_name}</div>")
                if ingredient.cas_number:
                    core_bits.append(f"<div class='muted'><b>cas</b>: {ingredient.cas_number}</div>")
                if ingredient.short_description:
                    core_bits.append(f"<div class='muted'><b>short</b>: {ingredient.short_description}</div>")
            items_html = ""
            if all_items and not show_quarantine:
                hidden = len([i for i in all_items if (getattr(i, "status", "") or "").strip().lower() != "active"])
                if hidden:
                    items_html += f"<div class='muted' style='margin-top:6px;'>({hidden} quarantined/rejected items hidden — toggle Quarantine to show)</div>"
            if items:
                items_html = (
                    "<div style='margin-top:8px;'><b>Items</b></div>"
                    + "".join(_render_item_block(i) for i in items)
                )
            details = "".join(core_bits) + items_html
            return f"<details><summary>{term}</summary><div style='margin-top:6px;'>{details}</div></details>"

        # Minimal HTML (no templates) to keep footprint tiny.
        table_rows = "\n".join(
            "<tr>"
            f"<td>{_render_term_cell(r.term)}</td>"
            f"<td>{r.term}</td>"
            f"<td>{getattr(r, 'seed_category', '') or ''}</td>"
            f"<td>{'true' if _to_bool_compiled(r.status) else 'false'}</td>"
            f"<td>{r.priority}</td>"
            f"<td>{r.status}</td>"
            f"<td>{_serialize_dt(r.last_updated)}</td>"
            "</tr>"
            for r in rows
        )

        prev_link = _qs(page=page - 1) if page > 1 else ""
        next_link = _qs(page=page + 1) if offset + page_size < total else ""

        return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Data Builder • Ingredient State DB</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 13px; }}
      th {{ background: #f6f6f6; text-align: left; position: sticky; top: 0; }}
      .muted {{ color: #666; font-size: 12px; }}
      .row {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: end; }}
      .card {{ padding: 12px; border: 1px solid #ddd; border-radius: 10px; }}
      input, select {{ padding: 6px 8px; }}
      a {{ text-decoration: none; }}
    </style>
  </head>
  <body>
    <h2>Ingredient compiler state</h2>
    <div class="muted">
      DB: <code>{database_manager.DB_PATH}</code>
    </div>

    <div class="row" style="margin-top: 12px;">
      <div class="card">
        <div><b>Summary</b></div>
        <div class="muted">total: {summary.get('total', 0)}</div>
        <div class="muted">pending: {summary.get('pending', 0)}</div>
        <div class="muted">processing: {summary.get('processing', 0)}</div>
        <div class="muted">completed: {summary.get('completed', 0)}</div>
        <div class="muted">error: {summary.get('error', 0)}</div>
        <hr style="border:none;border-top:1px solid #eee;margin:10px 0;"/>
        <div class="muted"><b>source_items</b>: {source_summary.get('total', 0)}</div>
        <div class="muted">linked: {source_summary.get('linked', 0)}</div>
        <div class="muted">orphans: {source_summary.get('orphan', 0)}</div>
        <div class="muted">review: {source_summary.get('review', 0)}</div>
      </div>

      <div class="card" style="flex: 1;">
        <form method="get" class="row">
          <div>
            <div class="muted">Search term</div>
            <input name="q" value="{q}" placeholder="e.g. acacia" />
          </div>
          <div>
            <div class="muted">Status</div>
            <select name="status">
              <option value="" {"selected" if status=="" else ""}>any</option>
              <option value="pending" {"selected" if status=="pending" else ""}>pending</option>
              <option value="processing" {"selected" if status=="processing" else ""}>processing</option>
              <option value="completed" {"selected" if status=="completed" else ""}>completed</option>
              <option value="error" {"selected" if status=="error" else ""}>error</option>
            </select>
          </div>
          <div>
            <div class="muted">Min priority</div>
            <input name="min_priority" value="{min_priority}" size="4" />
          </div>
          <div>
            <div class="muted">Max priority</div>
            <input name="max_priority" value="{max_priority}" size="4" />
          </div>
          <div>
            <div class="muted">Page size</div>
            <input name="page_size" value="{page_size}" size="4" />
          </div>
          <div>
            <button type="submit">Apply</button>
            <a href="/export.csv{_qs(page=None)}" style="margin-left: 10px;">Export CSV</a>
            <a href="/download.db" style="margin-left: 10px;">Download DB</a>
            <a href="/cursors.csv" style="margin-left: 10px;">Cursor CSV</a>
            <a href="/admin/variations" style="margin-left: 10px;">Admin: Variations</a>
          </div>
        </form>
        <div class="muted" style="margin-top: 8px;">
          Quarantine items are {"shown" if show_quarantine else "hidden"}.
          <a href="{_qs(show_quarantine='0' if show_quarantine else '1')}">Toggle</a>
        </div>
        <div class="muted" style="margin-top: 8px;">
          Showing {len(rows)} of {total}. Page {page}.
          {"<a href='" + prev_link + "'>Prev</a>" if prev_link else ""}
          {" | <a href='" + next_link + "'>Next</a>" if next_link else ""}
        </div>
      </div>
    </div>

    <h3 style="margin-top: 18px;">Rows</h3>
    <table>
      <thead>
        <tr>
          <th>name</th>
          <th>id</th>
          <th>seed_category</th>
          <th>is_compiled</th>
          <th>priority</th>
          <th>status</th>
          <th>last_updated</th>
        </tr>
      </thead>
      <tbody>
        {table_rows if table_rows else "<tr><td colspan='6' class='muted'>No rows match your filters.</td></tr>"}
      </tbody>
    </table>
  </body>
</html>
"""

    @app.get("/export.csv")
    def export_csv() -> Response:
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").strip().lower()
        min_priority = _parse_int(request.args.get("min_priority"), 1)
        max_priority = _parse_int(request.args.get("max_priority"), 10)

        database_manager.ensure_tables_exist()

        with database_manager.get_session() as session:
            query = session.query(database_manager.TaskQueue)
            if q:
                query = query.filter(database_manager.TaskQueue.term.ilike(f"%{q}%"))
            if status:
                query = query.filter(database_manager.TaskQueue.status == status)
            query = query.filter(database_manager.TaskQueue.priority >= min_priority)
            query = query.filter(database_manager.TaskQueue.priority <= max_priority)
            query = query.order_by(database_manager.TaskQueue.term.asc())
            rows = query.all()

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["name", "id", "seed_category", "is_compiled", "priority", "status", "last_updated"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "name": r.term,
                    "id": r.term,
                    "seed_category": getattr(r, "seed_category", "") or "",
                    "is_compiled": "true" if _to_bool_compiled(r.status) else "false",
                    "priority": r.priority,
                    "status": r.status,
                    "last_updated": _serialize_dt(r.last_updated),
                }
            )

        out = buf.getvalue()
        return Response(
            out,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=ingredient_state.csv"},
        )

    @app.get("/download.db")
    def download_db() -> Response:
        """Download the raw SQLite state DB for backup."""
        # Ensure tables exist so the DB file is created if missing.
        database_manager.ensure_tables_exist()

        path = Path(database_manager.DB_PATH).resolve()
        if not path.exists():
            return Response("State DB file not found.", status=404, mimetype="text/plain; charset=utf-8")

        return send_file(
            path,
            as_attachment=True,
            download_name="Final DB.db",
            mimetype="application/octet-stream",
            conditional=True,
        )

    @app.get("/cursors.csv")
    def export_cursors_csv() -> Response:
        """Export cursor progress per (seed_category, letter)."""
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        # Best-effort: keep in sync with stage-1 categories.
        try:
            from .term_collector import SEED_INGREDIENT_CATEGORIES  # type: ignore
            categories = list(SEED_INGREDIENT_CATEGORIES)
        except Exception:  # pragma: no cover
            with database_manager.get_session() as session:
                categories = sorted({(r[0] or "").strip() for r in session.query(database_manager.TaskQueue.seed_category).all() if (r[0] or "").strip()})
        if not categories:
            categories = ["(unset)"]

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["seed_category", "initial", "last_term", "pending_count", "completed_count"])
        writer.writeheader()

        with database_manager.get_session() as session:
            for cat in categories:
                for initial in letters:
                    base = session.query(database_manager.TaskQueue).filter(database_manager.TaskQueue.term.ilike(f"{initial}%"))
                    if cat != "(unset)":
                        base = base.filter(database_manager.TaskQueue.seed_category == cat)
                    last = (
                        base.order_by(database_manager.TaskQueue.term.collate("NOCASE").desc(), database_manager.TaskQueue.term.desc())
                        .with_entities(database_manager.TaskQueue.term)
                        .first()
                    )
                    pending_count = base.filter(database_manager.TaskQueue.status == "pending").count()
                    completed_count = base.filter(database_manager.TaskQueue.status == "completed").count()
                    writer.writerow(
                        {
                            "seed_category": cat,
                            "initial": initial,
                            "last_term": last[0] if last else "",
                            "pending_count": pending_count,
                            "completed_count": completed_count,
                        }
                    )

        out = buf.getvalue()
        return Response(
            out,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=cursor_progress.csv"},
        )

    @app.get("/admin/variations")
    def admin_variations() -> str:
        """List unapproved variations and counts of impacted items."""
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            vars_ = session.query(database_manager.VariationTerm).order_by(database_manager.VariationTerm.name.asc()).all()
            # Count items referencing each variation
            counts = {
                v: session.query(database_manager.IngredientItemRecord).filter(database_manager.IngredientItemRecord.variation == v).count()
                for v in {r.name for r in vars_}
            }
        rows = []
        for v in vars_:
            qname = _url_qs(v.name)
            rows.append(
                "<tr>"
                f"<td>{v.name}</td>"
                f"<td>{'true' if v.approved else 'false'}</td>"
                f"<td>{counts.get(v.name, 0)}</td>"
                f"<td><a href='/admin/variations/approve?name={qname}'>approve</a> | "
                f"<a href='/admin/variations/reject?name={qname}'>reject</a></td>"
                "</tr>"
            )
        table = "\n".join(rows) if rows else "<tr><td colspan='4' class='muted'>No variations.</td></tr>"
        return f"""
<!doctype html>
<html>
  <head><meta charset="utf-8"/><title>Admin • Variations</title></head>
  <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px;">
    <h2>Variations</h2>
    <div><a href="/">← Back</a></div>
    <p class="muted">Unapproved variations cause items to be quarantined until approved.</p>
    <table border="1" cellpadding="6" cellspacing="0">
      <thead><tr><th>name</th><th>approved</th><th>item_count</th><th>actions</th></tr></thead>
      <tbody>{table}</tbody>
    </table>
  </body>
</html>
"""

    @app.get("/admin/variations/approve")
    def approve_variation() -> Response:
        name = (request.args.get("name") or "").strip()
        if not name:
            return Response("Missing name", status=400)
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            v = session.get(database_manager.VariationTerm, name)
            if v is None:
                return Response("Not found", status=404)
            v.approved = True
            # Promote quarantined items with this variation to active if form is valid.
            session.query(database_manager.IngredientItemRecord).filter(
                database_manager.IngredientItemRecord.variation == name,
                database_manager.IngredientItemRecord.status == "quarantine",
            ).update({"approved": True, "status": "active", "needs_review_reason": None})
        return redirect("/admin/variations")

    @app.get("/admin/variations/reject")
    def reject_variation() -> Response:
        name = (request.args.get("name") or "").strip()
        if not name:
            return Response("Missing name", status=400)
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            v = session.get(database_manager.VariationTerm, name)
            if v is None:
                return Response("Not found", status=404)
            v.approved = False
            session.query(database_manager.IngredientItemRecord).filter(
                database_manager.IngredientItemRecord.variation == name,
            ).update({"approved": False, "status": "rejected", "needs_review_reason": f"Rejected variation: {name}"})
        return redirect("/admin/variations")

    @app.get("/ingredient/<path:term>")
    def ingredient_detail(term: str) -> str:
        database_manager.ensure_tables_exist()
        cleaned = (term or "").strip()
        if not cleaned:
            return "Missing term"

        with database_manager.get_session() as session:
            ing = session.get(database_manager.IngredientRecord, cleaned)
            if ing is None:
                return f"<html><body><a href='/'>← Back</a><h2>{escape(cleaned)}</h2><p class='muted'>No compiled ingredient record.</p></body></html>"

            items = (
                session.query(database_manager.IngredientItemRecord)
                .filter(database_manager.IngredientItemRecord.ingredient_term == cleaned)
                .order_by(database_manager.IngredientItemRecord.item_name.asc())
                .all()
            )
            item_ids = [i.id for i in items if getattr(i, "id", None) is not None]
            value_rows = []
            if item_ids:
                value_rows = (
                    session.query(database_manager.IngredientItemValue)
                    .filter(database_manager.IngredientItemValue.item_id.in_(item_ids))
                    .order_by(
                        database_manager.IngredientItemValue.item_id.asc(),
                        database_manager.IngredientItemValue.field.asc(),
                        database_manager.IngredientItemValue.value.asc(),
                    )
                    .all()
                )
            values_by_item: dict[int, dict[str, list[str]]] = {}
            for vr in value_rows:
                values_by_item.setdefault(vr.item_id, {}).setdefault(vr.field, []).append(vr.value)

        def _render_item_attrs(i: database_manager.IngredientItemRecord) -> str:
            tags = values_by_item.get(int(i.id), {}) if getattr(i, "id", None) is not None else {}
            tag_lines = []
            for field, values in tags.items():
                if not values:
                    continue
                preview = ", ".join(values[:18])
                suffix = f" … (+{len(values) - 18})" if len(values) > 18 else ""
                tag_lines.append(f"{field}: {preview}{suffix}")
            tag_blob = "\n".join(tag_lines)

            pretty = _safe_pretty_json(getattr(i, "item_json", "") or "")
            promoted = (
                f"shelf_life_days={getattr(i,'shelf_life_days', None)}, "
                f"ph_min={getattr(i,'ph_min', None)}, ph_max={getattr(i,'ph_max', None)}, "
                f"usage_leave_on_max={getattr(i,'usage_leave_on_max', None)}, usage_rinse_off_max={getattr(i,'usage_rinse_off_max', None)}"
            )

            pretty_html = (
                "<pre style='white-space:pre-wrap; font-size:12px; background:#fafafa; border:1px solid #eee; padding:10px; border-radius:8px;'>"
                f"{escape(pretty)}"
                "</pre>"
                if pretty
                else ""
            )
            tags_html = (
                "<pre style='white-space:pre-wrap; font-size:12px; background:#fff; border:1px solid #eee; padding:10px; border-radius:8px;'>"
                f"{escape(tag_blob)}"
                "</pre>"
                if tag_blob
                else ""
            )
            return (
                "<details>"
                "<summary>view</summary>"
                f"<div class='muted'><b>promoted</b>: {escape(promoted)}</div>"
                f"{pretty_html}{tags_html}"
                "</details>"
            )

        item_rows = "".join(
            "<tr>"
            f"<td>{escape(str(i.id))}</td>"
            f"<td>{escape(i.item_name)}</td>"
            f"<td>{escape(i.variation or '')}</td>"
            f"<td>{escape(i.physical_form or '')}</td>"
            f"<td>{escape(i.status)}</td>"
            f"<td>{escape(i.needs_review_reason or '')}</td>"
            f"<td>{_render_item_attrs(i)}</td>"
            f"<td><a href='/item/{i.id}/edit'>edit</a></td>"
            "</tr>"
            for i in items
        ) or "<tr><td colspan='8' class='muted'>No items.</td></tr>"

        return f"""
<!doctype html>
<html>
  <head><meta charset="utf-8"/><title>Ingredient • {escape(cleaned)}</title></head>
  <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px;">
    <h2>{escape(cleaned)}</h2>
    <div><a href="/">← Back</a></div>
    <h3>Base</h3>
    <div class="muted"><b>ingredient_category</b>: {escape(getattr(ing, 'ingredient_category', '') or '')}</div>
    <div class="muted"><b>origin</b>: {escape(getattr(ing, 'origin', '') or '')}</div>
    <div class="muted"><b>refinement_level</b>: {escape(getattr(ing, 'refinement_level', '') or '')}</div>
    <div class="muted"><b>derived_from</b>: {escape(getattr(ing, 'derived_from', '') or '')}</div>
    <div class="muted"><b>inci</b>: {escape(getattr(ing, 'inci_name', '') or '')}</div>
    <div class="muted"><b>cas</b>: {escape(getattr(ing, 'cas_number', '') or '')}</div>

    <h3 style="margin-top:18px;">Items</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%;">
      <thead>
        <tr>
          <th>id</th><th>item_name</th><th>variation</th><th>physical_form</th><th>status</th><th>needs_review_reason</th><th>attributes</th><th></th>
        </tr>
      </thead>
      <tbody>
        {item_rows}
      </tbody>
    </table>
  </body>
</html>
"""

    @app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
    def edit_item(item_id: int):  # type: ignore[no-untyped-def]
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            item = session.get(database_manager.IngredientItemRecord, item_id)
            if item is None:
                return Response("Item not found", status=404)
            ing = session.get(database_manager.IngredientRecord, item.ingredient_term)
            if ing is None:
                return Response("Ingredient not found", status=404)

            if request.method == "POST":
                variation = (request.form.get("variation") or "").strip()
                physical_form = (request.form.get("physical_form") or "").strip()
                variation_bypass = (request.form.get("variation_bypass") or "").strip().lower() in {"1", "true", "yes", "on"}
                form_bypass = (request.form.get("form_bypass") or "").strip().lower() in {"1", "true", "yes", "on"}
                status = (request.form.get("status") or item.status or "active").strip().lower()
                if status not in {"active", "quarantine", "rejected"}:
                    status = "active"
                needs_review_reason = (request.form.get("needs_review_reason") or "").strip() or None

                # Validate physical form against curated enum; blank if invalid.
                if physical_form and physical_form not in database_manager.PHYSICAL_FORMS:
                    physical_form = ""

                # Variation approval check; quarantine if unapproved.
                approved = True
                vrow = session.get(database_manager.VariationTerm, variation) if variation else None
                if variation and vrow is not None and not bool(vrow.approved):
                    approved = False
                    status = "quarantine"
                    needs_review_reason = needs_review_reason or f"Unapproved variation: {variation}"
                # Allow form-less items only when the user explicitly sets form_bypass.
                if not physical_form and not form_bypass:
                    approved = False
                    status = "quarantine"
                    needs_review_reason = needs_review_reason or "Missing/invalid physical_form"

                # Apply edits.
                item.variation = variation
                item.physical_form = physical_form
                item.variation_bypass = variation_bypass
                item.form_bypass = form_bypass
                item.approved = approved
                item.status = status
                item.needs_review_reason = needs_review_reason

                # Regenerate display name deterministically.
                item.item_name = database_manager.derive_item_display_name(
                    base_term=ing.term,
                    variation=variation,
                    variation_bypass=variation_bypass,
                    physical_form=physical_form,
                    form_bypass=form_bypass,
                )

                return redirect(f"/ingredient/{_url_path(ing.term)}")

        # GET render
        checked_v = "checked" if item.variation_bypass else ""
        checked_f = "checked" if item.form_bypass else ""

        return f"""
<!doctype html>
<html>
  <head><meta charset="utf-8"/><title>Edit Item • {escape(str(item_id))}</title></head>
  <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px;">
    <h2>Edit Item</h2>
    <div><a href="/ingredient/{_url_path(ing.term)}">← Back to ingredient</a></div>
    <div class="muted"><b>base</b>: {escape(ing.term)}</div>
    <div class="muted"><b>current item_name</b>: {escape(item.item_name)}</div>
    <form method="post" style="margin-top: 12px;">
      <div style="margin-bottom: 10px;">
        <label>Variation<br/>
          <input name="variation" value="{escape(item.variation or '')}" style="width: 420px;" />
        </label>
      </div>
      <div style="margin-bottom: 10px;">
        <label>Physical form<br/>
          <input name="physical_form" value="{escape(item.physical_form or '')}" style="width: 220px;" />
        </label>
        <div class="muted">Must match curated enum; invalid values will blank (quarantine unless Form bypass is set).</div>
      </div>
      <div style="margin-bottom: 10px;">
        <label><input type="checkbox" name="variation_bypass" value="1" {checked_v}/> Variation bypass</label>
      </div>
      <div style="margin-bottom: 10px;">
        <label><input type="checkbox" name="form_bypass" value="1" {checked_f}/> Form bypass</label>
      </div>
      <div style="margin-bottom: 10px;">
        <label>Status<br/>
          <select name="status">
            <option value="active" {"selected" if item.status=="active" else ""}>active</option>
            <option value="quarantine" {"selected" if item.status=="quarantine" else ""}>quarantine</option>
            <option value="rejected" {"selected" if item.status=="rejected" else ""}>rejected</option>
          </select>
        </label>
      </div>
      <div style="margin-bottom: 10px;">
        <label>Needs review reason<br/>
          <input name="needs_review_reason" value="{escape(item.needs_review_reason or '')}" style="width: 640px;" />
        </label>
      </div>
      <button type="submit">Save</button>
    </form>
  </body>
</html>
"""

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="View/export the ingredient Final DB.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--db-path", default="", help="Override FINAL_DB_PATH for this portal run")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    db_path = Path(args.db_path).resolve() if args.db_path else None
    app = create_app(db_path=db_path)
    # Note: this is a dev portal; use a reverse proxy if exposing beyond localhost.
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()

