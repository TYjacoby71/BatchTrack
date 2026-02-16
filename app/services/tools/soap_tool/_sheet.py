"""Soap formula sheet and CSV builders.

Synopsis:
Builds export-ready CSV rows/text and printable HTML from computed soap tool
result payloads in a single backend authority.

Glossary:
- Formula sheet: Human-readable print view of recipe outputs.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ._print_policy import clamp_print_target_pct

UNIT_FACTORS = {
    "g": 1.0,
    "oz": 28.3495,
    "lb": 453.592,
}

_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parents[3] / "templates")),
    autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
)


def _render_sheet_template(template_name: str, **context: Any) -> str:
    template = _TEMPLATE_ENV.get_template(template_name)
    return template.render(**context)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if cleaned == "":
                return float(default)
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_unit(unit_display: str) -> str:
    token = str(unit_display or "g").lower().strip()
    return token if token in UNIT_FACTORS else "g"


# --- Unit conversion helper ---
# Purpose: Convert gram values to requested display unit.
# Inputs: Value in grams and display unit token.
# Outputs: Numeric value in target unit.
def _from_grams(value_g: float, unit_display: str) -> float:
    unit = _safe_unit(unit_display)
    factor = UNIT_FACTORS.get(unit, 1.0)
    return (_to_float(value_g, 0.0)) / factor


# --- Weight formatting helper ---
# Purpose: Render display weight text from gram values.
# Inputs: Value in grams and display unit token.
# Outputs: Formatted weight string.
def _format_weight(value_g: float, unit_display: str) -> str:
    unit = _safe_unit(unit_display)
    value = _from_grams(value_g, unit)
    if value <= 0:
        return "--"
    return f"{round(value, 2)} {unit}"


# --- Percent formatting helper ---
# Purpose: Render percentage display text.
# Inputs: Numeric percent value.
# Outputs: Formatted percent string.
def _format_percent(value: float) -> str:
    return f"{round(_to_float(value, 0.0), 1)}%"


def _resolve_total_lye_g(result: dict, extra_lye: float) -> float:
    base_adjusted = result.get("lye_adjusted_base_g")
    if base_adjusted is not None:
        return _to_float(base_adjusted, 0.0) + _to_float(extra_lye, 0.0)
    return _to_float(result.get("lye_adjusted_g"), 0.0) + _to_float(extra_lye, 0.0)


def _build_assumption_notes(result: dict, additives: dict, unit_display: str) -> list[str]:
    notes: list[str] = []
    extra_lye = _to_float(additives.get("citricLyeG"), 0.0)
    citric_g = _to_float(additives.get("citricG"), 0.0)
    lye_type = str(result.get("lye_type") or "NaOH").upper()

    if extra_lye > 0 and citric_g > 0:
        if lye_type == "KOH":
            notes.append("Citric-acid lye adjustment used 0.71 x citric acid because KOH was selected.")
        else:
            notes.append("Citric-acid lye adjustment used 0.624 x citric acid because NaOH was selected.")
        notes.append(f"{_format_weight(extra_lye, unit_display)} lye added extra to accommodate the extra citrus.")

    if bool(result.get("used_sap_fallback")):
        notes.append("Average SAP fallback was used for oils missing SAP values.")

    if str(result.get("lye_selected") or "").upper() == "KOH90":
        notes.append("KOH90 selection assumes 90% lye purity.")

    oils = result.get("oils") or []
    has_decimal_sap = any(0.0 < _to_float((oil or {}).get("sap_koh"), 0.0) <= 1.0 for oil in oils)
    if has_decimal_sap:
        notes.append("SAP values at or below 1.0 were treated as decimal SAP and converted to mg KOH/g.")

    return notes


def _build_oil_rows(result: dict, unit_display: str) -> list[dict[str, str]]:
    total_oils = _to_float(result.get("total_oils_g"), 0.0)
    rows: list[dict[str, str]] = []
    for oil in result.get("oils") or []:
        grams = _to_float((oil or {}).get("grams"), 0.0)
        pct = ((grams / total_oils) * 100.0) if total_oils > 0 else 0.0
        rows.append(
            {
                "name": str((oil or {}).get("name") or "Oil"),
                "weight": _format_weight(grams, unit_display),
                "percent": _format_percent(pct),
            }
        )
    return rows


def _build_fragrance_rows(additives: dict, unit_display: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in additives.get("fragranceRows") or []:
        record = row if isinstance(row, dict) else {}
        rows.append(
            {
                "name": str(record.get("name") or "Fragrance/Essential Oils"),
                "weight": _format_weight(_to_float(record.get("grams"), 0.0), unit_display),
                "percent": _format_percent(_to_float(record.get("pct"), 0.0)),
            }
        )
    return rows


def _build_additive_rows(additives: dict, unit_display: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name_key, grams_key, pct_key, fallback in [
        ("lactateName", "lactateG", "lactatePct", "Sodium Lactate"),
        ("sugarName", "sugarG", "sugarPct", "Sugar"),
        ("saltName", "saltG", "saltPct", "Salt"),
        ("citricName", "citricG", "citricPct", "Citric Acid"),
    ]:
        grams = _to_float(additives.get(grams_key), 0.0)
        if grams <= 0:
            continue
        rows.append(
            {
                "name": str(additives.get(name_key) or fallback),
                "weight": _format_weight(grams, unit_display),
                "percent": _format_percent(_to_float(additives.get(pct_key), 0.0)),
            }
        )
    return rows


def _build_formula_summary_items(result: dict, additives: dict, quality_report: dict, unit_display: str) -> list[dict[str, str]]:
    total_oils = _to_float(result.get("total_oils_g"), 0.0)
    extra_lye = _to_float(additives.get("citricLyeG"), 0.0)
    lye_total = _resolve_total_lye_g(result, extra_lye)
    lye_total_text = _format_weight(lye_total, unit_display)
    if extra_lye > 0:
        lye_total_text = f"{lye_total_text}*"

    sat_unsat = quality_report.get("sat_unsat") or {}
    sat_value = _to_float(sat_unsat.get("saturated"), 0.0)
    unsat_value = _to_float(sat_unsat.get("unsaturated"), 0.0)
    sat_unsat_text = f"{round(sat_value, 0)} : {round(unsat_value, 0)}" if (sat_value + unsat_value) > 0 else "--"
    water_ratio = _to_float(result.get("water_lye_ratio"), 0.0)
    water_ratio_text = f"{round(water_ratio, 2)}:1" if water_ratio > 0 else "--"
    iodine = _to_float(quality_report.get("iodine"), 0.0)
    iodine_text = round(iodine, 1) if iodine > 0 else "--"
    ins = _to_float(quality_report.get("ins"), 0.0)
    ins_text = round(ins, 1) if ins > 0 else "--"
    fragrance_pct = _to_float(additives.get("fragrancePct"), 0.0)
    fragrance_ratio_text = _format_percent(fragrance_pct) if fragrance_pct > 0 else "--"
    fragrance_weight = _to_float(additives.get("fragranceG"), 0.0)
    batch_yield = _to_float((result.get("results_card") or {}).get("batch_yield_g"), 0.0)

    return [
        {"label": "Lye type", "value": str(result.get("lye_type") or "--")},
        {"label": "Superfat", "value": _format_percent(_to_float(result.get("superfat_pct"), 0.0))},
        {"label": "Lye purity", "value": _format_percent(_to_float(result.get("lye_purity_pct"), 0.0))},
        {"label": "Total oils", "value": _format_weight(total_oils, unit_display)},
        {"label": "Total lye", "value": lye_total_text},
        {"label": "Water", "value": _format_weight(_to_float(result.get("water_g"), 0.0), unit_display)},
        {"label": "Batch yield", "value": _format_weight(batch_yield, unit_display)},
        {"label": "Water method", "value": str(result.get("water_method") or "--")},
        {"label": "Water %", "value": _format_percent(_to_float(result.get("water_pct"), 0.0))},
        {"label": "Lye concentration", "value": _format_percent(_to_float(result.get("lye_concentration_pct"), 0.0))},
        {"label": "Water : Lye Ratio", "value": water_ratio_text},
        {"label": "Sat : Unsat Ratio", "value": sat_unsat_text},
        {"label": "Iodine", "value": str(iodine_text)},
        {"label": "INS", "value": str(ins_text)},
        {"label": "Fragrance Ratio", "value": fragrance_ratio_text},
        {"label": "Fragrance Weight", "value": _format_weight(fragrance_weight, unit_display)},
    ]


def _build_print_summary_items(result: dict, unit_display: str) -> list[dict[str, str]]:
    total_oils = _to_float(result.get("total_oils_g"), 0.0)
    batch_yield = _to_float((result.get("results_card") or {}).get("batch_yield_g"), 0.0)
    return [
        {"label": "Lye type", "value": str(result.get("lye_type") or "--")},
        {"label": "Superfat", "value": _format_percent(_to_float(result.get("superfat_pct"), 0.0))},
        {"label": "Lye purity", "value": _format_percent(_to_float(result.get("lye_purity_pct"), 0.0))},
        {"label": "Total oils", "value": _format_weight(total_oils, unit_display)},
        {"label": "Water", "value": _format_weight(_to_float(result.get("water_g"), 0.0), unit_display)},
        {"label": "Batch yield", "value": _format_weight(batch_yield, unit_display)},
        {"label": "Water method", "value": str(result.get("water_method") or "--")},
        {"label": "Lye concentration", "value": _format_percent(_to_float(result.get("lye_concentration_pct"), 0.0))},
    ]


# --- CSV rows builder ---
# Purpose: Build canonical soap formula CSV row matrix.
# Inputs: Computed soap result dictionary and unit display.
# Outputs: List of CSV rows.
def build_formula_csv_rows(result: dict, unit_display: str) -> list[list[str | float]]:
    unit = _safe_unit(unit_display)
    total_oils = _to_float(result.get("total_oils_g"), 0.0)
    additives = result.get("additives") or {}
    extra_lye = _to_float(additives.get("citricLyeG"), 0.0)
    assumption_notes = _build_assumption_notes(result, additives, unit)
    rows: list[list[str | float]] = [["section", "name", "quantity", "unit", "percent"]]
    rows.append(["Summary", "Lye Type", result.get("lye_type") or "", "", ""])
    rows.append(["Summary", "Superfat", round(_to_float(result.get("superfat_pct"), 0.0), 2), "%", ""])
    rows.append(["Summary", "Lye Purity", round(_to_float(result.get("lye_purity_pct"), 0.0), 1), "%", ""])
    rows.append(["Summary", "Water Method", result.get("water_method") or "", "", ""])
    rows.append(["Summary", "Water %", round(_to_float(result.get("water_pct"), 0.0), 1), "%", ""])
    rows.append(["Summary", "Lye Concentration", round(_to_float(result.get("lye_concentration_pct"), 0.0), 1), "%", ""])
    rows.append(["Summary", "Water Ratio", round(_to_float(result.get("water_lye_ratio"), 0.0), 2), "", ""])
    rows.append(["Summary", "Total Oils", round(_from_grams(total_oils, unit), 2), unit, ""])
    rows.append(
        [
            "Summary",
            "Batch Yield",
            round(_from_grams(_to_float((result.get("results_card") or {}).get("batch_yield_g"), 0.0), unit), 2),
            unit,
            "",
        ]
    )

    for oil in result.get("oils") or []:
        record = oil if isinstance(oil, dict) else {}
        grams = _to_float(record.get("grams"), 0.0)
        pct = round((grams / total_oils) * 100.0, 2) if total_oils > 0 else ""
        rows.append(["Oils", record.get("name") or "Oil", round(_from_grams(grams, unit), 2), unit, pct])

    lye_total_display = _resolve_total_lye_g(result, extra_lye)
    if lye_total_display > 0:
        lye_name = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
        if extra_lye > 0:
            lye_name = f"{lye_name}*"
        rows.append(["Lye", lye_name, round(_from_grams(lye_total_display, unit), 2), unit, ""])

    water_g = _to_float(result.get("water_g"), 0.0)
    if water_g > 0:
        rows.append(["Water", "Distilled Water", round(_from_grams(water_g, unit), 2), unit, ""])

    for row in additives.get("fragranceRows") or []:
        record = row if isinstance(row, dict) else {}
        rows.append(
            [
                "Fragrance",
                record.get("name") or "Fragrance/Essential Oils",
                round(_from_grams(_to_float(record.get("grams"), 0.0), unit), 2),
                unit,
                round(_to_float(record.get("pct"), 0.0), 2),
            ]
        )

    additive_entries = [
        (
            additives.get("lactateName") or "Sodium Lactate",
            _to_float(additives.get("lactateG"), 0.0),
            _to_float(additives.get("lactatePct"), 0.0),
        ),
        (
            additives.get("sugarName") or "Sugar",
            _to_float(additives.get("sugarG"), 0.0),
            _to_float(additives.get("sugarPct"), 0.0),
        ),
        (
            additives.get("saltName") or "Salt",
            _to_float(additives.get("saltG"), 0.0),
            _to_float(additives.get("saltPct"), 0.0),
        ),
        (
            additives.get("citricName") or "Citric Acid",
            _to_float(additives.get("citricG"), 0.0),
            _to_float(additives.get("citricPct"), 0.0),
        ),
    ]
    for name, grams, pct in additive_entries:
        if grams <= 0:
            continue
        rows.append(["Additives", name, round(_from_grams(grams, unit), 2), unit, round(pct, 2)])

    for note in assumption_notes:
        rows.append(["Notes", f"* {note}", "", "", ""])
    return rows


# --- CSV text serializer ---
# Purpose: Convert formula row matrix to CSV text.
# Inputs: CSV row matrix.
# Outputs: CSV text string.
def build_formula_csv_text(rows: list[list[str | float]]) -> str:
    def _escape(value: str | float) -> str:
        text = "" if value is None else str(value)
        if any(ch in text for ch in ['"', ",", "\n"]):
            escaped = text.replace('"', '""')
            return f'"{escaped}"'
        return text

    return "\n".join(",".join(_escape(col) for col in row) for row in rows)


# --- Printable sheet HTML builder ---
# Purpose: Build printable formula-sheet HTML from computed result data.
# Inputs: Computed result dictionary and display unit token.
# Outputs: HTML document string.
def build_formula_sheet_html(result: dict, unit_display: str, normalization_note: str = "") -> str:
    unit = _safe_unit(unit_display)
    additives = result.get("additives") or {}
    quality_report = result.get("quality_report") or {}
    assumption_notes = _build_assumption_notes(result, additives, unit)
    lye_label = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
    extra_lye = _to_float(additives.get("citricLyeG"), 0.0)
    lye_total = _resolve_total_lye_g(result, extra_lye)
    lye_label_display = f"{lye_label}*" if extra_lye > 0 else lye_label
    lye_total_text = _format_weight(lye_total, unit)
    if extra_lye > 0:
        lye_total_text = f"{lye_total_text}*"

    context = {
        "generated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "normalization_note": (normalization_note or "").strip(),
        "summary_items": _build_formula_summary_items(result, additives, quality_report, unit),
        "oil_rows": _build_oil_rows(result, unit),
        "fragrance_rows": _build_fragrance_rows(additives, unit),
        "additive_rows": _build_additive_rows(additives, unit),
        "lye_label_display": lye_label_display,
        "lye_total_text": lye_total_text,
        "water_text": _format_weight(_to_float(result.get("water_g"), 0.0), unit),
        "assumption_notes": assumption_notes,
    }
    return _render_sheet_template("tools/soaps/exports/soap_formula_sheet.html", **context)


def build_print_sheet_html(result: dict, unit_display: str, normalization_note: str = "") -> str:
    unit = _safe_unit(unit_display)
    additives = result.get("additives") or {}
    assumption_notes = _build_assumption_notes(result, additives, unit)
    lye_label = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
    extra_lye = _to_float(additives.get("citricLyeG"), 0.0)
    lye_total = _resolve_total_lye_g(result, extra_lye)
    lye_label_display = f"{lye_label}*" if extra_lye > 0 else lye_label
    lye_total_text = _format_weight(lye_total, unit)
    if extra_lye > 0:
        lye_total_text = f"{lye_total_text}*"

    context = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "normalization_note": (normalization_note or "").strip(),
        "summary_items": _build_print_summary_items(result, unit),
        "oil_rows": _build_oil_rows(result, unit),
        "fragrance_rows": _build_fragrance_rows(additives, unit),
        "additive_rows": _build_additive_rows(additives, unit),
        "lye_label_display": lye_label_display,
        "lye_total_text": lye_total_text,
        "water_text": _format_weight(_to_float(result.get("water_g"), 0.0), unit),
        "assumption_notes": assumption_notes,
    }
    return _render_sheet_template("tools/soaps/exports/soap_print_sheet.html", **context)


def _pick(mapping: dict, *keys: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return default


def _coerce_client_calc_snapshot(calc_snapshot: dict) -> dict:
    if not isinstance(calc_snapshot, dict):
        return {}

    oils_raw = _pick(calc_snapshot, "oils", default=[])
    oils: list[dict] = []
    for oil in oils_raw if isinstance(oils_raw, list) else []:
        if not isinstance(oil, dict):
            continue
        oils.append(
            {
                "name": str(_pick(oil, "name", default="Oil") or "Oil"),
                "grams": _to_float(_pick(oil, "grams"), 0.0),
                "sap_koh": _to_float(_pick(oil, "sap_koh", "sapKoh"), 0.0),
                "iodine": _to_float(_pick(oil, "iodine"), 0.0),
                "fatty_profile": _pick(oil, "fatty_profile", "fattyProfile", default={}) or {},
                "global_item_id": _pick(oil, "global_item_id", "globalItemId"),
                "default_unit": _pick(oil, "default_unit", "defaultUnit"),
                "ingredient_category_name": _pick(oil, "ingredient_category_name", "ingredientCategoryName"),
            }
        )

    additives_raw = _pick(calc_snapshot, "additives", default={})
    additives_source = additives_raw if isinstance(additives_raw, dict) else {}
    fragrance_rows_raw = _pick(additives_source, "fragranceRows", default=[])
    fragrance_rows: list[dict] = []
    for row in fragrance_rows_raw if isinstance(fragrance_rows_raw, list) else []:
        if not isinstance(row, dict):
            continue
        fragrance_rows.append(
            {
                "name": str(_pick(row, "name", default="Fragrance/Essential Oils") or "Fragrance/Essential Oils"),
                "grams": _to_float(_pick(row, "grams"), 0.0),
                "pct": _to_float(_pick(row, "pct"), 0.0),
            }
        )

    quality_report_raw = _pick(calc_snapshot, "qualityReport", "quality_report", default={})
    quality_report = quality_report_raw if isinstance(quality_report_raw, dict) else {}

    results_card_raw = _pick(calc_snapshot, "results_card", "resultsCard", default={})
    results_card = results_card_raw if isinstance(results_card_raw, dict) else {}
    batch_yield = _to_float(
        _pick(
            calc_snapshot,
            "batchYield",
            "batch_yield_g",
            default=_pick(results_card, "batch_yield_g", "batchYieldG", default=0.0),
        ),
        0.0,
    )

    lye_adjusted_base_raw = _pick(calc_snapshot, "lyeAdjustedBase", "lye_adjusted_base_g", default=None)
    lye_adjusted_base = None
    if lye_adjusted_base_raw not in (None, "", []):
        lye_adjusted_base = _to_float(lye_adjusted_base_raw, 0.0)

    coerced_additives = {
        "fragrancePct": _to_float(_pick(additives_source, "fragrancePct"), 0.0),
        "lactatePct": _to_float(_pick(additives_source, "lactatePct"), 0.0),
        "sugarPct": _to_float(_pick(additives_source, "sugarPct"), 0.0),
        "saltPct": _to_float(_pick(additives_source, "saltPct"), 0.0),
        "citricPct": _to_float(_pick(additives_source, "citricPct"), 0.0),
        "fragranceG": _to_float(_pick(additives_source, "fragranceG"), 0.0),
        "lactateG": _to_float(_pick(additives_source, "lactateG"), 0.0),
        "sugarG": _to_float(_pick(additives_source, "sugarG"), 0.0),
        "saltG": _to_float(_pick(additives_source, "saltG"), 0.0),
        "citricG": _to_float(_pick(additives_source, "citricG"), 0.0),
        "citricLyeG": _to_float(_pick(additives_source, "citricLyeG"), 0.0),
        "fragranceRows": fragrance_rows,
        "lactateName": str(_pick(additives_source, "lactateName", default="Sodium Lactate") or "Sodium Lactate"),
        "sugarName": str(_pick(additives_source, "sugarName", default="Sugar") or "Sugar"),
        "saltName": str(_pick(additives_source, "saltName", default="Salt") or "Salt"),
        "citricName": str(_pick(additives_source, "citricName", default="Citric Acid") or "Citric Acid"),
    }
    if coerced_additives["fragrancePct"] <= 0 and fragrance_rows:
        coerced_additives["fragrancePct"] = sum(_to_float(row.get("pct"), 0.0) for row in fragrance_rows)

    return {
        "total_oils_g": _to_float(_pick(calc_snapshot, "totalOils", "total_oils_g"), 0.0),
        "oils": oils,
        "lye_type": str(_pick(calc_snapshot, "lyeType", "lye_type", default="NaOH") or "NaOH"),
        "lye_selected": str(_pick(calc_snapshot, "lyeSelected", "lye_selected", default="NaOH") or "NaOH"),
        "superfat_pct": _to_float(_pick(calc_snapshot, "superfat", "superfat_pct"), 0.0),
        "lye_purity_pct": _to_float(_pick(calc_snapshot, "purity", "lye_purity_pct"), 100.0),
        "lye_pure_g": _to_float(_pick(calc_snapshot, "lyePure", "lye_pure_g"), 0.0),
        "lye_adjusted_base_g": lye_adjusted_base,
        "lye_adjusted_g": _to_float(_pick(calc_snapshot, "lyeAdjusted", "lye_adjusted_g"), 0.0),
        "water_g": _to_float(_pick(calc_snapshot, "water", "water_g"), 0.0),
        "water_method": str(_pick(calc_snapshot, "waterMethod", "water_method", default="percent") or "percent"),
        "water_pct": _to_float(_pick(calc_snapshot, "waterPct", "water_pct"), 0.0),
        "lye_concentration_pct": _to_float(_pick(calc_snapshot, "lyeConcentration", "lye_concentration_pct"), 0.0),
        "water_lye_ratio": _to_float(_pick(calc_snapshot, "waterRatio", "water_lye_ratio"), 0.0),
        "used_sap_fallback": bool(_pick(calc_snapshot, "usedSapFallback", "used_sap_fallback", default=False)),
        "additives": coerced_additives,
        "quality_report": quality_report,
        "results_card": {
            "batch_yield_g": batch_yield,
        },
    }


def _scale_result_for_print(result: dict, scale_factor: float, target_batch_yield_g: float) -> dict:
    if not math.isfinite(scale_factor) or scale_factor <= 0:
        return deepcopy(result)
    scaled = deepcopy(result)
    for key in ["total_oils_g", "lye_pure_g", "lye_adjusted_g", "water_g"]:
        scaled[key] = _to_float(scaled.get(key), 0.0) * scale_factor
    if scaled.get("lye_adjusted_base_g") is not None:
        scaled["lye_adjusted_base_g"] = _to_float(scaled.get("lye_adjusted_base_g"), 0.0) * scale_factor

    oils = []
    for oil in scaled.get("oils") or []:
        row = dict(oil or {})
        row["grams"] = _to_float(row.get("grams"), 0.0) * scale_factor
        oils.append(row)
    scaled["oils"] = oils

    additives = dict(scaled.get("additives") or {})
    for key in ["lactateG", "sugarG", "saltG", "citricG", "citricLyeG", "fragranceG"]:
        additives[key] = _to_float(additives.get(key), 0.0) * scale_factor
    fragrance_rows = []
    for row in additives.get("fragranceRows") or []:
        record = dict(row or {})
        record["grams"] = _to_float(record.get("grams"), 0.0) * scale_factor
        fragrance_rows.append(record)
    additives["fragranceRows"] = fragrance_rows
    scaled["additives"] = additives

    results_card = dict(scaled.get("results_card") or {})
    results_card["batch_yield_g"] = _to_float(target_batch_yield_g, 0.0)
    scaled["results_card"] = results_card
    return scaled


def build_normalized_print_sheet_payload(
    calc_snapshot: dict,
    mold_capacity_g: float,
    target_fill_pct: float,
    unit_display: str,
) -> dict | None:
    result = _coerce_client_calc_snapshot(calc_snapshot)
    mold_capacity = _to_float(mold_capacity_g, 0.0)
    current_batch_yield = _to_float((result.get("results_card") or {}).get("batch_yield_g"), 0.0)
    if mold_capacity <= 0 or current_batch_yield <= 0:
        return None

    desired_pct = clamp_print_target_pct(target_fill_pct)
    target_batch_yield = mold_capacity * (desired_pct / 100.0)
    if target_batch_yield <= 0:
        return None
    scale_factor = target_batch_yield / current_batch_yield
    if not math.isfinite(scale_factor) or scale_factor <= 0:
        return None

    normalized_result = _scale_result_for_print(result, scale_factor, target_batch_yield)
    note = (
        f"Normalized to {round(desired_pct, 1)}% mold fill "
        f"({_format_weight(target_batch_yield, unit_display)} target batch)."
    )
    return {
        "sheet_html": build_print_sheet_html(normalized_result, unit_display, normalization_note=note),
        "normalization_note": note,
        "target_fill_pct": desired_pct,
        "target_batch_yield_g": target_batch_yield,
        "scale_factor": scale_factor,
    }


__all__ = [
    "build_formula_csv_rows",
    "build_formula_csv_text",
    "build_formula_sheet_html",
    "build_print_sheet_html",
    "build_normalized_print_sheet_payload",
]

