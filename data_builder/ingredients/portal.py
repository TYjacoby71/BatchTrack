"""Lightweight viewer/exporter for the ingredient compiler state DB.

This is intentionally small and self-contained: it reads `compiler_state.db`
and renders a basic table + CSV export so you can *see* progress and back it up.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from flask import Flask, Response, request, send_file
from flask import redirect

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


def create_app(db_path: Optional[Path] = None) -> Flask:
    app = Flask(__name__)

    # Ensure DB exists / schema present.
    if db_path is not None:
        os.environ["COMPILER_DB_PATH"] = str(db_path)
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
            item_rows = (
                session.query(database_manager.IngredientItemRecord)
                .filter(database_manager.IngredientItemRecord.ingredient_term.in_(page_terms))
                .filter(True if show_quarantine else database_manager.IngredientItemRecord.status == "active")
                .order_by(database_manager.IngredientItemRecord.ingredient_term.asc(), database_manager.IngredientItemRecord.item_name.asc())
                .all()
            )
            items_by_term: dict[str, list[database_manager.IngredientItemRecord]] = {}
            for item in item_rows:
                items_by_term.setdefault(item.ingredient_term, []).append(item)

            # Summary counts
            summary = database_manager.get_queue_summary()

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

        def _render_term_cell(term: str) -> str:
            ingredient = ingredients_by_term.get(term)
            items = items_by_term.get(term, [])
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
            if items:
                rows_html = "".join(
                    "<tr>"
                    f"<td>{i.item_name}</td>"
                    f"<td>{i.variation or ''}</td>"
                    f"<td>{i.physical_form or ''}</td>"
                    "</tr>"
                    for i in items
                )
                items_html = (
                    "<div style='margin-top:8px;'><b>Items</b></div>"
                    "<table style='margin-top:6px; width:100%; border-collapse:collapse;'>"
                    "<thead><tr><th>item_name</th><th>variation</th><th>physical_form</th></tr></thead>"
                    f"<tbody>{rows_html}</tbody>"
                    "</table>"
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
            <a href="/normalized_terms.csv" style="margin-left: 10px;">Normalized terms CSV</a>
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
            headers={"Content-Disposition": "attachment; filename=ingredient_compiler_state.csv"},
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
            download_name="compiler_state.db",
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

    @app.get("/normalized_terms.csv")
    def export_normalized_terms_csv() -> Response:
        """Export normalized base terms from normalized_terms table."""
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            rows = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc()).all()

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["term", "seed_category", "botanical_name", "inci_name", "cas_number", "description", "normalized_at"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "term": r.term,
                    "seed_category": r.seed_category or "",
                    "botanical_name": r.botanical_name or "",
                    "inci_name": r.inci_name or "",
                    "cas_number": r.cas_number or "",
                    "description": r.description or "",
                    "normalized_at": _serialize_dt(r.normalized_at),
                }
            )
        out = buf.getvalue()
        return Response(
            out,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=normalized_terms.csv"},
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
            rows.append(
                "<tr>"
                f"<td>{v.name}</td>"
                f"<td>{'true' if v.approved else 'false'}</td>"
                f"<td>{counts.get(v.name, 0)}</td>"
                f"<td><a href='/admin/variations/approve?name={v.name}'>approve</a> | "
                f"<a href='/admin/variations/reject?name={v.name}'>reject</a></td>"
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

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="View/export the ingredient compiler_state.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--db-path", default="", help="Override COMPILER_DB_PATH for this portal run")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    db_path = Path(args.db_path).resolve() if args.db_path else None
    app = create_app(db_path=db_path)
    # Note: this is a dev portal; use a reverse proxy if exposing beyond localhost.
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()

