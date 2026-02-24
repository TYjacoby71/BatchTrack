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

from app.extensions import db
from app.models import Recipe
from app.services.exports import ExportService
from app.utils.permissions import require_permission

exports_bp = Blueprint("exports", __name__, url_prefix="/exports")


# --- Recipe Or 404 ---
# Purpose: Define the top-level behavior of `_recipe_or_404` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
def _recipe_or_404(recipe_id: int) -> Recipe:
    recipe = db.session.get(Recipe, recipe_id)
    if recipe is None:
        abort(404)
    user_org = getattr(current_user, "organization_id", None)
    if user_org and recipe.organization_id != user_org:
        abort(403)
    if (
        user_org
        and recipe.organization_id == user_org
        and not recipe.org_origin_purchased
    ):
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


# --- Tool Draft ---
# Purpose: Define the top-level behavior of `_tool_draft` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
def _tool_draft():
    return session.get("tool_draft") or {}


# --- Render Tool ---
# Purpose: Define the top-level behavior of `_render_tool` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
def _render_tool(template: str):
    return render_template(template, tool_draft=_tool_draft(), source="tool")


# =========================================================
# RECIPE HTML EXPORTS
# =========================================================
# --- Soap INCI (HTML) ---
# Purpose: Render soap INCI sheet for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/soap-inci")
@login_required
@require_permission("reports.export")
def soap_inci_recipe(recipe_id: int):
    return render_template(
        "exports/soap_inci.html", recipe=_recipe_or_404(recipe_id), source="recipe"
    )


# --- Candle label (HTML) ---
# Purpose: Render candle label sheet for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/candle-label")
@login_required
@require_permission("reports.export")
def candle_label_recipe(recipe_id: int):
    return render_template(
        "exports/candle_label.html", recipe=_recipe_or_404(recipe_id), source="recipe"
    )


# --- Baker sheet (HTML) ---
# Purpose: Render baker sheet for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet")
@login_required
@require_permission("reports.export")
def baker_sheet_recipe(recipe_id: int):
    return render_template(
        "exports/baker_sheet.html", recipe=_recipe_or_404(recipe_id), source="recipe"
    )


# --- Lotion INCI (HTML) ---
# Purpose: Render lotion INCI sheet for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci")
@login_required
@require_permission("reports.export")
def lotion_inci_recipe(recipe_id: int):
    return render_template(
        "exports/lotion_inci.html", recipe=_recipe_or_404(recipe_id), source="recipe"
    )


# =========================================================
# TOOL HTML EXPORTS
# =========================================================
# --- Soap INCI tool (HTML) ---
# Purpose: Render soap INCI sheet for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/soaps/inci")
def soap_inci_tool():
    return _render_tool("exports/soap_inci.html")


# --- Candle label tool (HTML) ---
# Purpose: Render candle label sheet for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/candles/label")
def candle_label_tool():
    return _render_tool("exports/candle_label.html")


# --- Baker sheet tool (HTML) ---
# Purpose: Render baker sheet for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/baker/sheet")
def baker_sheet_tool():
    return _render_tool("exports/baker_sheet.html")


# --- Lotion INCI tool (HTML) ---
# Purpose: Render lotion INCI sheet for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/lotions/inci")
def lotion_inci_tool():
    return _render_tool("exports/lotion_inci.html")


# --- Csv Response ---
# Purpose: Define the top-level behavior of `_csv_response` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
def _csv_response(content: str) -> Response:
    return Response(content, mimetype="text/csv")


# --- Pdf Response ---
# Purpose: Define the top-level behavior of `_pdf_response` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
def _pdf_response(content: bytes) -> Response:
    return Response(content, mimetype="application/pdf")


# =========================================================
# RECIPE FILE EXPORTS
# =========================================================
# --- Soap INCI CSV ---
# Purpose: Export soap INCI CSV for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/soap-inci.csv")
@login_required
@require_permission("reports.export")
def soap_inci_recipe_csv(recipe_id: int):
    csv_text = ExportService.soap_inci_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# --- Soap INCI PDF ---
# Purpose: Export soap INCI PDF for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/soap-inci.pdf")
@login_required
@require_permission("reports.export")
def soap_inci_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.soap_inci_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# --- Candle label CSV ---
# Purpose: Export candle label CSV for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/candle-label.csv")
@login_required
@require_permission("reports.export")
def candle_label_recipe_csv(recipe_id: int):
    csv_text = ExportService.candle_label_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# --- Candle label PDF ---
# Purpose: Export candle label PDF for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/candle-label.pdf")
@login_required
@require_permission("reports.export")
def candle_label_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.candle_label_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# --- Baker sheet CSV ---
# Purpose: Export baker sheet CSV for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet.csv")
@login_required
@require_permission("reports.export")
def baker_sheet_recipe_csv(recipe_id: int):
    csv_text = ExportService.baker_sheet_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# --- Baker sheet PDF ---
# Purpose: Export baker sheet PDF for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/baker-sheet.pdf")
@login_required
@require_permission("reports.export")
def baker_sheet_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.baker_sheet_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# --- Lotion INCI CSV ---
# Purpose: Export lotion INCI CSV for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci.csv")
@login_required
@require_permission("reports.export")
def lotion_inci_recipe_csv(recipe_id: int):
    csv_text = ExportService.lotion_inci_csv(recipe=_recipe_or_404(recipe_id))
    return _csv_response(csv_text)


# --- Lotion INCI PDF ---
# Purpose: Export lotion INCI PDF for a recipe.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/recipe/<int:recipe_id>/lotion-inci.pdf")
@login_required
@require_permission("reports.export")
def lotion_inci_recipe_pdf(recipe_id: int):
    pdf_bytes = ExportService.lotion_inci_pdf(recipe=_recipe_or_404(recipe_id))
    return _pdf_response(pdf_bytes)


# =========================================================
# TOOL FILE EXPORTS
# =========================================================
# --- Soap INCI tool CSV ---
# Purpose: Export soap INCI CSV for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/soaps/inci.csv")
def soap_inci_tool_csv():
    csv_text = ExportService.soap_inci_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# --- Soap INCI tool PDF ---
# Purpose: Export soap INCI PDF for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/soaps/inci.pdf")
def soap_inci_tool_pdf():
    pdf_bytes = ExportService.soap_inci_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


# --- Candle label tool CSV ---
# Purpose: Export candle label CSV for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/candles/label.csv")
def candle_label_tool_csv():
    csv_text = ExportService.candle_label_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# --- Candle label tool PDF ---
# Purpose: Export candle label PDF for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/candles/label.pdf")
def candle_label_tool_pdf():
    pdf_bytes = ExportService.candle_label_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


# --- Baker sheet tool CSV ---
# Purpose: Export baker sheet CSV for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/baker/sheet.csv")
def baker_sheet_tool_csv():
    csv_text = ExportService.baker_sheet_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# --- Baker sheet tool PDF ---
# Purpose: Export baker sheet PDF for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/baker/sheet.pdf")
def baker_sheet_tool_pdf():
    pdf_bytes = ExportService.baker_sheet_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)


# --- Lotion INCI tool CSV ---
# Purpose: Export lotion INCI CSV for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/lotions/inci.csv")
def lotion_inci_tool_csv():
    csv_text = ExportService.lotion_inci_csv(tool_draft=_tool_draft())
    return _csv_response(csv_text)


# --- Lotion INCI tool PDF ---
# Purpose: Export lotion INCI PDF for tool draft.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@exports_bp.route("/tool/lotions/inci.pdf")
def lotion_inci_tool_pdf():
    pdf_bytes = ExportService.lotion_inci_pdf(tool_draft=_tool_draft())
    return _pdf_response(pdf_bytes)
