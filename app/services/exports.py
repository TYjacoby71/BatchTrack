from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from flask import render_template, request

logger = logging.getLogger(__name__)



def _extract_lines_from_recipe(recipe) -> Dict[str, List[Dict[str, Any]]]:
    try:
        ings = [
            {
                "name": (
                    ri.inventory_item.name
                    if getattr(ri, "inventory_item", None)
                    else ""
                ),
                "quantity": float(getattr(ri, "quantity", 0.0) or 0.0),
                "unit": getattr(ri, "unit", "") or "",
            }
            for ri in (getattr(recipe, "recipe_ingredients", []) or [])
        ]
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/exports.py:22", exc_info=True)
        ings = []
    try:
        cons = [
            {
                "name": (
                    rc.inventory_item.name
                    if getattr(rc, "inventory_item", None)
                    else ""
                ),
                "quantity": float(getattr(rc, "quantity", 0.0) or 0.0),
                "unit": getattr(rc, "unit", "") or "",
            }
            for rc in (getattr(recipe, "recipe_consumables", []) or [])
        ]
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/exports.py:37", exc_info=True)
        cons = []
    return {"ingredients": ings, "consumables": cons}


def _extract_lines_from_draft(draft: dict) -> Dict[str, List[Dict[str, Any]]]:
    ings = draft.get("ingredients") or []
    cons = draft.get("consumables") or []
    return {
        "ingredients": [
            {
                "name": (ln.get("name") or "").strip(),
                "quantity": float(ln.get("quantity") or 0.0),
                "unit": (ln.get("unit") or "").strip() or "",
            }
            for ln in ings
        ],
        "consumables": [
            {
                "name": (ln.get("name") or "").strip(),
                "quantity": float(ln.get("quantity") or 0.0),
                "unit": (ln.get("unit") or "").strip() or "",
            }
            for ln in cons
        ],
    }


def _csv(rows: List[List[str]]) -> str:
    # Simple CSV serializer; no quoting complexities for now
    out_lines = []
    for row in rows:
        out_lines.append(
            ",".join([str(col).replace("\n", " ").replace("\r", " ") for col in row])
        )
    return "\n".join(out_lines) + "\n"


class ExportService:
    @staticmethod
    def soap_inci_csv(recipe=None, tool_draft: Optional[dict] = None) -> str:
        # INCI style: list all ingredient names with totals if possible
        if recipe is not None:
            data = _extract_lines_from_recipe(recipe)
            title = getattr(recipe, "name", "Recipe")
        else:
            data = _extract_lines_from_draft(tool_draft or {})
            title = (tool_draft or {}).get("name") or "Soap Draft"
        rows = [[f"Soap INCI - {title}"]]
        rows.append(["Name", "Quantity", "Unit"])
        for ln in data["ingredients"]:
            rows.append([ln["name"], ln["quantity"], ln["unit"]])
        return _csv(rows)

    @staticmethod
    def candle_label_csv(recipe=None, tool_draft: Optional[dict] = None) -> str:
        if recipe is not None:
            data = _extract_lines_from_recipe(recipe)
            title = getattr(recipe, "name", "Recipe")
            cd = getattr(recipe, "category_data", {}) or {}
        else:
            data = _extract_lines_from_draft(tool_draft or {})
            title = (tool_draft or {}).get("name") or "Candle Draft"
            cd = (tool_draft or {}).get("category_data") or {}
        rows = [[f"Candle Label Summary - {title}"]]
        rows.append(["Field", "Value"])
        # Include key candle fields if present
        for k in [
            "candle_wax_g",
            "candle_fragrance_pct",
            "candle_vessel_ml",
            "vessel_fill_pct",
            "candle_count",
        ]:
            v = cd.get(k)
            if v is not None and v != "":
                rows.append([k, v])
        rows.append([])
        rows.append(["Ingredients"])
        rows.append(["Name", "Quantity", "Unit"])
        for ln in data["ingredients"]:
            rows.append([ln["name"], ln["quantity"], ln["unit"]])
        return _csv(rows)

    @staticmethod
    def baker_sheet_csv(recipe=None, tool_draft: Optional[dict] = None) -> str:
        if recipe is not None:
            data = _extract_lines_from_recipe(recipe)
            title = getattr(recipe, "name", "Recipe")
            cd = getattr(recipe, "category_data", {}) or {}
        else:
            data = _extract_lines_from_draft(tool_draft or {})
            title = (tool_draft or {}).get("name") or "Baker Draft"
            cd = (tool_draft or {}).get("category_data") or {}
        rows = [[f"Baker Batch Sheet - {title}"]]
        rows.append(["Field", "Value"])
        for k in [
            "baker_base_flour_g",
            "baker_water_pct",
            "baker_salt_pct",
            "baker_yeast_pct",
        ]:
            v = cd.get(k)
            if v is not None and v != "":
                rows.append([k, v])
        rows.append([])
        rows.append(["Ingredients"])
        rows.append(["Name", "Quantity", "Unit"])
        for ln in data["ingredients"]:
            rows.append([ln["name"], ln["quantity"], ln["unit"]])
        return _csv(rows)

    @staticmethod
    def lotion_inci_csv(recipe=None, tool_draft: Optional[dict] = None) -> str:
        if recipe is not None:
            data = _extract_lines_from_recipe(recipe)
            title = getattr(recipe, "name", "Recipe")
        else:
            data = _extract_lines_from_draft(tool_draft or {})
            title = (tool_draft or {}).get("name") or "Lotion Draft"
        rows = [[f"Lotion INCI - {title}"]]
        rows.append(["Name", "Quantity", "Unit"])
        for ln in data["ingredients"]:
            rows.append([ln["name"], ln["quantity"], ln["unit"]])
        return _csv(rows)

    @staticmethod
    def _render_html(template_name: str, context: Dict[str, Any]) -> str:
        return render_template(template_name, **context)

    @staticmethod
    def soap_inci_pdf(recipe=None, tool_draft: Optional[dict] = None) -> bytes:
        html = ExportService._render_html(
            "exports/soap_inci.html",
            {"recipe": recipe, "tool_draft": tool_draft, "source": "pdf"},
        )
        return ExportService._html_to_pdf(html)

    @staticmethod
    def candle_label_pdf(recipe=None, tool_draft: Optional[dict] = None) -> bytes:
        html = ExportService._render_html(
            "exports/candle_label.html",
            {"recipe": recipe, "tool_draft": tool_draft, "source": "pdf"},
        )
        return ExportService._html_to_pdf(html)

    @staticmethod
    def baker_sheet_pdf(recipe=None, tool_draft: Optional[dict] = None) -> bytes:
        html = ExportService._render_html(
            "exports/baker_sheet.html",
            {"recipe": recipe, "tool_draft": tool_draft, "source": "pdf"},
        )
        return ExportService._html_to_pdf(html)

    @staticmethod
    def lotion_inci_pdf(recipe=None, tool_draft: Optional[dict] = None) -> bytes:
        html = ExportService._render_html(
            "exports/lotion_inci.html",
            {"recipe": recipe, "tool_draft": tool_draft, "source": "pdf"},
        )
        return ExportService._html_to_pdf(html)

    @staticmethod
    def _html_to_pdf(html: str) -> bytes:
        # Preferred: WeasyPrint (HTML/CSS → PDF)
        try:
            from weasyprint import HTML

            base_url = request.host_url if request else None
            return HTML(string=html, base_url=base_url).write_pdf()
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/exports.py:207", exc_info=True)
            pass
        # Fallback: wrap HTML bytes (minimal) to keep route functional
        return html.encode("utf-8")
