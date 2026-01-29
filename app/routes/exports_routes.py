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
    return recipe


def _tool_draft():
    return session.get("tool_draft") or {}


def _render_tool(template: str):
    return render_template(template, tool_draft=_tool_draft(), source="tool")


@exports_bp.route("/recipe/<int:recipe_id>/soap-inci")
@login_required
@require_permission('reports.export')
def soap_inci_recipe(recipe_id: int):
    return render_template("exports/soap_inci.html", recipe=_recipe_or_404(recipe_id), source="recipe")


@exports_bp.route("/recipe/<int:recipe_id>/candle-label")
@login_required
@require_permission('reports.export')
def candle_label_recipe(recipe_id: int):
    return render_template("exports/candle_label.html", recipe=_recipe_or_404(recipe_id), source="recipe")


@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet")
@login_required
@require_permission('reports.export')
def baker_sheet_recipe(recipe_id: int):
    return render_template("exports/baker_sheet.html", recipe=_recipe_or_404(recipe_id), source="recipe")


@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci")
@login_required
@require_permission('reports.export')
def lotion_inci_recipe(recipe_id: int):
    return render_template("exports/lotion_inci.html", recipe=_recipe_or_404(recipe_id), source="recipe")


@exports_bp.route("/tool/soaps/inci")
def soap_inci_tool():
    return _render_tool("exports/soap_inci.html")


@exports_bp.route("/tool/candles/label")
def candle_label_tool():
    return _render_tool("exports/candle_label.html")


@exports_bp.route("/tool/baker/sheet")
def baker_sheet_tool():
    return _render_tool("exports/baker_sheet.html")


@exports_bp.route("/tool/lotions/inci")
def lotion_inci_tool():
    return _render_tool("exports/lotion_inci.html")


def _csv_response(content: str) -> Response:
    return Response(content, mimetype="text/csv")


def _pdf_response(content: bytes) -> Response:
    return Response(content, mimetype="application/pdf")


@exports_bp.route("/recipe/<int:recipe_id>/soap-inci.csv")
@login_required
@require_permission('reports.export')
def soap_inci_recipe_csv(recipe_id: int):
    csv_text = ExportService.soap_inci_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


@exports_bp.route("/recipe/<int:recipe_id>/soap-inci.pdf")
@login_required
@require_permission('reports.export')
def soap_inci_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.soap_inci_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


@exports_bp.route("/recipe/<int:recipe_id>/candle-label.csv")
@login_required
@require_permission('reports.export')
def candle_label_recipe_csv(recipe_id: int):
    csv_text = ExportService.candle_label_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


@exports_bp.route("/recipe/<int:recipe_id>/candle-label.pdf")
@login_required
@require_permission('reports.export')
def candle_label_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.candle_label_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet.csv")
@login_required
@require_permission('reports.export')
def baker_sheet_recipe_csv(recipe_id: int):
    csv_text = ExportService.baker_sheet_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet.pdf")
@login_required
@require_permission('reports.export')
def baker_sheet_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.baker_sheet_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci.csv")
@login_required
@require_permission('reports.export')
def lotion_inci_recipe_csv(recipe_id: int):
    csv_text = ExportService.lotion_inci_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci.pdf")
@login_required
@require_permission('reports.export')
def lotion_inci_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.lotion_inci_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


@exports_bp.route("/tool/soaps/inci.csv")
def soap_inci_tool_csv():
    csv_text = ExportService.soap_inci_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


@exports_bp.route("/tool/soaps/inci.pdf")
def soap_inci_tool_pdf():
    pdf_bytes = ExportService.soap_inci_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


@exports_bp.route("/tool/candles/label.csv")
def candle_label_tool_csv():
    csv_text = ExportService.candle_label_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


@exports_bp.route("/tool/candles/label.pdf")
def candle_label_tool_pdf():
    pdf_bytes = ExportService.candle_label_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


@exports_bp.route("/tool/baker/sheet.csv")
def baker_sheet_tool_csv():
    csv_text = ExportService.baker_sheet_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


@exports_bp.route("/tool/baker/sheet.pdf")
def baker_sheet_tool_pdf():
    pdf_bytes = ExportService.baker_sheet_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


@exports_bp.route("/tool/lotions/inci.csv")
def lotion_inci_tool_csv():
    csv_text = ExportService.lotion_inci_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


@exports_bp.route("/tool/lotions/inci.pdf")
def lotion_inci_tool_pdf():
    pdf_bytes = ExportService.lotion_inci_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)
