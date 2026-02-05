"""Export routes for recipe and tool documents.

Synopsis:
Serve HTML, CSV, and PDF exports for recipe labels and regulatory sheets.

Glossary:
- INCI: International Nomenclature of Cosmetic Ingredients listing.
- Baker sheet: Production worksheet for batch prep.
"""

from __future__ import annotations

from flask import Blueprint, Response, abort, render_template, session
from flask_login import current_user, login_required
from app.utils.permissions import require_permission

from app.extensions import db
from app.models import Recipe
from app.services.exports import ExportService

exports_bp = Blueprint("exports", __name__, url_prefix="/exports")


def _recipe_or_404(recipe_id: int) -> Recipe:
    recipe = db.session.get(Recipe, recipe_id)
    if recipe is None:
        abort(404)
    user_org = getattr(current_user, "organization_id", None)
    if user_org and recipe.organization_id != user_org:
        abort(403)
    if user_org and recipe.organization_id == user_org and not recipe.org_origin_purchased:
        updated = False
        if recipe.org_origin_recipe_id != recipe.id:
            recipe.org_origin_recipe_id = recipe.id
            updated = True
        if recipe.org_origin_type in (None, "authored"):
            recipe.org_origin_type = "published"
            updated = True
        if updated:
            db.session.commit()
    return recipe


def _tool_draft():
    return session.get("tool_draft") or {}


def _render_tool(template: str):
    return render_template(template, tool_draft=_tool_draft(), source="tool")


# Route 1: Render soap INCI sheet (HTML).
@exports_bp.route("/recipe/<int:recipe_id>/soap-inci")
@login_required
@require_permission('reports.export')
def soap_inci_recipe(recipe_id: int):
    return render_template("exports/soap_inci.html", recipe=_recipe_or_404(recipe_id), source="recipe")


# Route 2: Render candle label sheet (HTML).
@exports_bp.route("/recipe/<int:recipe_id>/candle-label")
@login_required
@require_permission('reports.export')
def candle_label_recipe(recipe_id: int):
    return render_template("exports/candle_label.html", recipe=_recipe_or_404(recipe_id), source="recipe")


# Route 3: Render baker sheet (HTML).
@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet")
@login_required
@require_permission('reports.export')
def baker_sheet_recipe(recipe_id: int):
    return render_template("exports/baker_sheet.html", recipe=_recipe_or_404(recipe_id), source="recipe")


# Route 4: Render lotion INCI sheet (HTML).
@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci")
@login_required
@require_permission('reports.export')
def lotion_inci_recipe(recipe_id: int):
    return render_template("exports/lotion_inci.html", recipe=_recipe_or_404(recipe_id), source="recipe")


# Route 5: Render tool soap INCI sheet (HTML).
@exports_bp.route("/tool/soaps/inci")
def soap_inci_tool():
    return _render_tool("exports/soap_inci.html")


# Route 6: Render tool candle label sheet (HTML).
@exports_bp.route("/tool/candles/label")
def candle_label_tool():
    return _render_tool("exports/candle_label.html")


# Route 7: Render tool baker sheet (HTML).
@exports_bp.route("/tool/baker/sheet")
def baker_sheet_tool():
    return _render_tool("exports/baker_sheet.html")


# Route 8: Render tool lotion INCI sheet (HTML).
@exports_bp.route("/tool/lotions/inci")
def lotion_inci_tool():
    return _render_tool("exports/lotion_inci.html")


def _csv_response(content: str) -> Response:
    return Response(content, mimetype="text/csv")


def _pdf_response(content: bytes) -> Response:
    return Response(content, mimetype="application/pdf")


# Route 9: Export soap INCI CSV.
@exports_bp.route("/recipe/<int:recipe_id>/soap-inci.csv")
@login_required
@require_permission('reports.export')
def soap_inci_recipe_csv(recipe_id: int):
    csv_text = ExportService.soap_inci_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# Route 10: Export soap INCI PDF.
@exports_bp.route("/recipe/<int:recipe_id>/soap-inci.pdf")
@login_required
@require_permission('reports.export')
def soap_inci_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.soap_inci_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# Route 11: Export candle label CSV.
@exports_bp.route("/recipe/<int:recipe_id>/candle-label.csv")
@login_required
@require_permission('reports.export')
def candle_label_recipe_csv(recipe_id: int):
    csv_text = ExportService.candle_label_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# Route 12: Export candle label PDF.
@exports_bp.route("/recipe/<int:recipe_id>/candle-label.pdf")
@login_required
@require_permission('reports.export')
def candle_label_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.candle_label_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# Route 13: Export baker sheet CSV.
@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet.csv")
@login_required
@require_permission('reports.export')
def baker_sheet_recipe_csv(recipe_id: int):
    csv_text = ExportService.baker_sheet_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# Route 14: Export baker sheet PDF.
@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet.pdf")
@login_required
@require_permission('reports.export')
def baker_sheet_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.baker_sheet_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# Route 15: Export lotion INCI CSV.
@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci.csv")
@login_required
@require_permission('reports.export')
def lotion_inci_recipe_csv(recipe_id: int):
    csv_text = ExportService.lotion_inci_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# Route 16: Export lotion INCI PDF.
@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci.pdf")
@login_required
@require_permission('reports.export')
def lotion_inci_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.lotion_inci_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# Route 17: Export tool soap INCI CSV.
@exports_bp.route("/tool/soaps/inci.csv")
def soap_inci_tool_csv():
    csv_text = ExportService.soap_inci_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# Route 18: Export tool soap INCI PDF.
@exports_bp.route("/tool/soaps/inci.pdf")
def soap_inci_tool_pdf():
    pdf_bytes = ExportService.soap_inci_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


# Route 19: Export tool candle label CSV.
@exports_bp.route("/tool/candles/label.csv")
def candle_label_tool_csv():
    csv_text = ExportService.candle_label_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# Route 20: Export tool candle label PDF.
@exports_bp.route("/tool/candles/label.pdf")
def candle_label_tool_pdf():
    pdf_bytes = ExportService.candle_label_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


# Route 21: Export tool baker sheet CSV.
@exports_bp.route("/tool/baker/sheet.csv")
def baker_sheet_tool_csv():
    csv_text = ExportService.baker_sheet_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# Route 22: Export tool baker sheet PDF.
@exports_bp.route("/tool/baker/sheet.pdf")
def baker_sheet_tool_pdf():
    pdf_bytes = ExportService.baker_sheet_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


# Route 23: Export tool lotion INCI CSV.
@exports_bp.route("/tool/lotions/inci.csv")
def lotion_inci_tool_csv():
    csv_text = ExportService.lotion_inci_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# Route 24: Export tool lotion INCI PDF.
@exports_bp.route("/tool/lotions/inci.pdf")
def lotion_inci_tool_pdf():
    pdf_bytes = ExportService.lotion_inci_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)
