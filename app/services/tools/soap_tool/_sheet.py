"""Soap formula sheet and CSV builders.

Synopsis:
Builds export-ready CSV rows/text and printable HTML from computed soap tool
result payloads in a single backend authority.

Glossary:
- Formula sheet: Human-readable print view of recipe outputs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

UNIT_FACTORS = {
    "g": 1.0,
    "oz": 28.3495,
    "lb": 453.592,
}

APP_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(str(APP_ROOT / "templates")),
    autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
)
_PRINT_SHEET_TEMPLATE = "tools/soaps/exports/print_sheet.html"


# --- Unit conversion helper ---
# Purpose: Convert gram values to requested display unit.
# Inputs: Value in grams and display unit token.
# Outputs: Numeric value in target unit.
def _from_grams(value_g: float, unit_display: str) -> float:
    factor = UNIT_FACTORS.get(unit_display, 1.0)
    return (value_g or 0.0) / factor


# --- Weight formatting helper ---
# Purpose: Render display weight text from gram values.
# Inputs: Value in grams and display unit token.
# Outputs: Formatted weight string.
def _format_weight(value_g: float, unit_display: str) -> str:
    value = _from_grams(value_g, unit_display)
    if value <= 0:
        return "--"
    return f"{round(value, 2)} {unit_display}"


# --- Percent formatting helper ---
# Purpose: Render percentage display text.
# Inputs: Numeric percent value.
# Outputs: Formatted percent string.
def _format_percent(value: float) -> str:
    return f"{round(value or 0.0, 1)}%"


# --- Total lye resolver ---
# Purpose: Resolve final lye grams including optional citric-acid extra lye.
# Inputs: Computation result payload and extra-lye grams.
# Outputs: Total lye grams for export display.
def _resolve_total_lye_g(result: dict, extra_lye: float) -> float:
    base_adjusted = result.get("lye_adjusted_base_g")
    if base_adjusted is not None:
        return float(base_adjusted or 0.0) + extra_lye
    return float(result.get("lye_adjusted_g") or 0.0) + extra_lye


# --- Assumption notes compiler ---
# Purpose: Build export footnotes describing conversion/assumption choices.
# Inputs: Computation result payload, additive payload, and display unit token.
# Outputs: Ordered note strings rendered in CSV and print exports.
def _build_assumption_notes(result: dict, additives: dict, unit_display: str) -> list[str]:
    notes: list[str] = []
    extra_lye = float(additives.get("citricLyeG") or 0.0)
    citric_g = float(additives.get("citricG") or 0.0)
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
    has_decimal_sap = any(0.0 < float((oil or {}).get("sap_koh") or 0.0) <= 1.0 for oil in oils)
    if has_decimal_sap:
        notes.append("SAP values at or below 1.0 were treated as decimal SAP and converted to mg KOH/g.")

    return notes


# --- CSV rows builder ---
# Purpose: Build canonical soap formula CSV row matrix.
# Inputs: Computed soap result dictionary and unit display.
# Outputs: List of CSV rows.
def build_formula_csv_rows(result: dict, unit_display: str) -> list[list[str | float]]:
    total_oils = float(result.get("total_oils_g") or 0.0)
    additives = result.get("additives") or {}
    extra_lye = float(additives.get("citricLyeG") or 0.0)
    assumption_notes = _build_assumption_notes(result, additives, unit_display)
    rows: list[list[str | float]] = [["section", "name", "quantity", "unit", "percent"]]
    rows.append(["Summary", "Lye Type", result.get("lye_type") or "", "", ""])
    rows.append(["Summary", "Superfat", round(float(result.get("superfat_pct") or 0.0), 2), "%", ""])
    rows.append(["Summary", "Lye Purity", round(float(result.get("lye_purity_pct") or 0.0), 1), "%", ""])
    rows.append(["Summary", "Water Method", result.get("water_method") or "", "", ""])
    rows.append(["Summary", "Water %", round(float(result.get("water_pct") or 0.0), 1), "%", ""])
    rows.append(["Summary", "Lye Concentration", round(float(result.get("lye_concentration_pct") or 0.0), 1), "%", ""])
    rows.append(["Summary", "Water Ratio", round(float(result.get("water_lye_ratio") or 0.0), 2), "", ""])
    rows.append(["Summary", "Total Oils", round(_from_grams(total_oils, unit_display), 2), unit_display, ""])
    rows.append(
        [
            "Summary",
            "Batch Yield",
            round(_from_grams(float((result.get("results_card") or {}).get("batch_yield_g") or 0.0), unit_display), 2),
            unit_display,
            "",
        ]
    )

    for oil in result.get("oils") or []:
        grams = float(oil.get("grams") or 0.0)
        pct = round((grams / total_oils) * 100.0, 2) if total_oils > 0 else ""
        rows.append(["Oils", oil.get("name") or "Oil", round(_from_grams(grams, unit_display), 2), unit_display, pct])

    lye_total_display = _resolve_total_lye_g(result, extra_lye)
    if lye_total_display > 0:
        lye_name = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
        if extra_lye > 0:
            lye_name = f"{lye_name}*"
        rows.append(["Lye", lye_name, round(_from_grams(lye_total_display, unit_display), 2), unit_display, ""])

    water_g = float(result.get("water_g") or 0.0)
    if water_g > 0:
        rows.append(["Water", "Distilled Water", round(_from_grams(water_g, unit_display), 2), unit_display, ""])

    for row in additives.get("fragranceRows") or []:
        rows.append(
            [
                "Fragrance",
                row.get("name") or "Fragrance/Essential Oils",
                round(_from_grams(float(row.get("grams") or 0.0), unit_display), 2),
                unit_display,
                round(float(row.get("pct") or 0.0), 2),
            ]
        )

    additive_entries = [
        (additives.get("lactateName") or "Sodium Lactate", float(additives.get("lactateG") or 0.0), float(additives.get("lactatePct") or 0.0)),
        (additives.get("sugarName") or "Sugar", float(additives.get("sugarG") or 0.0), float(additives.get("sugarPct") or 0.0)),
        (additives.get("saltName") or "Salt", float(additives.get("saltG") or 0.0), float(additives.get("saltPct") or 0.0)),
        (additives.get("citricName") or "Citric Acid", float(additives.get("citricG") or 0.0), float(additives.get("citricPct") or 0.0)),
    ]
    for name, grams, pct in additive_entries:
        if grams <= 0:
            continue
        rows.append(["Additives", name, round(_from_grams(grams, unit_display), 2), unit_display, round(pct, 2)])

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
def build_formula_sheet_html(result: dict, unit_display: str) -> str:
    total_oils = float(result.get("total_oils_g") or 0.0)
    additives = result.get("additives") or {}
    quality_report = result.get("quality_report") or {}
    assumption_notes = _build_assumption_notes(result, additives, unit_display)
    oils = result.get("oils") or []
    fragrance_rows = additives.get("fragranceRows") or []
    additive_rows = []
    for name_key, grams_key, pct_key, fallback in [
        ("lactateName", "lactateG", "lactatePct", "Sodium Lactate"),
        ("sugarName", "sugarG", "sugarPct", "Sugar"),
        ("saltName", "saltG", "saltPct", "Salt"),
        ("citricName", "citricG", "citricPct", "Citric Acid"),
    ]:
        grams = float(additives.get(grams_key) or 0.0)
        if grams <= 0:
            continue
        additive_rows.append(
            {
                "name": additives.get(name_key) or fallback,
                "grams": grams,
                "pct": float(additives.get(pct_key) or 0.0),
            }
        )

    lye_label = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
    extra_lye = float(additives.get("citricLyeG") or 0.0)
    lye_total = _resolve_total_lye_g(result, extra_lye)
    lye_label_display = f"{lye_label}*" if extra_lye > 0 else lye_label
    lye_total_text = _format_weight(lye_total, unit_display)
    if extra_lye > 0:
        lye_total_text = f"{lye_total_text}*"
    sat_unsat = quality_report.get("sat_unsat") or {}
    sat_value = float(sat_unsat.get("saturated") or 0.0)
    unsat_value = float(sat_unsat.get("unsaturated") or 0.0)
    sat_unsat_text = f"{round(sat_value, 0)} : {round(unsat_value, 0)}" if (sat_value + unsat_value) > 0 else "--"
    water_ratio = float(result.get("water_lye_ratio") or 0.0)
    water_ratio_text = f"{round(water_ratio, 2)}:1" if water_ratio > 0 else "--"
    iodine = float(quality_report.get("iodine") or 0.0)
    iodine_text = round(iodine, 1) if iodine > 0 else "--"
    ins = float(quality_report.get("ins") or 0.0)
    ins_text = round(ins, 1) if ins > 0 else "--"
    fragrance_pct = float(additives.get("fragrancePct") or 0.0)
    fragrance_ratio_text = _format_percent(fragrance_pct) if fragrance_pct > 0 else "--"
    fragrance_weight = float(additives.get("fragranceG") or 0.0)
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    batch_yield = float((result.get("results_card") or {}).get("batch_yield_g") or 0.0)
    summary_items = [
        {"label": "Lye type", "value": str(result.get("lye_type") or "--")},
        {"label": "Superfat", "value": _format_percent(float(result.get("superfat_pct") or 0.0))},
        {"label": "Lye purity", "value": _format_percent(float(result.get("lye_purity_pct") or 0.0))},
        {"label": "Total oils", "value": _format_weight(total_oils, unit_display)},
        {"label": "Total lye", "value": lye_total_text},
        {"label": "Water", "value": _format_weight(float(result.get("water_g") or 0.0), unit_display)},
        {"label": "Batch yield", "value": _format_weight(batch_yield, unit_display)},
        {"label": "Water method", "value": str(result.get("water_method") or "--")},
        {"label": "Water %", "value": _format_percent(float(result.get("water_pct") or 0.0))},
        {"label": "Lye concentration", "value": _format_percent(float(result.get("lye_concentration_pct") or 0.0))},
        {"label": "Water : Lye Ratio", "value": water_ratio_text},
        {"label": "Sat : Unsat Ratio", "value": sat_unsat_text},
        {"label": "Iodine", "value": iodine_text},
        {"label": "INS", "value": ins_text},
        {"label": "Fragrance Ratio", "value": fragrance_ratio_text},
        {"label": "Fragrance Weight", "value": _format_weight(fragrance_weight, unit_display)},
    ]

    oil_rows = [
        {
            "name": str(oil.get("name") or "Oil"),
            "weight": _format_weight(float(oil.get("grams") or 0.0), unit_display),
            "percent": _format_percent(((float(oil.get("grams") or 0.0) / total_oils) * 100.0) if total_oils > 0 else 0.0),
        }
        for oil in oils
    ]
    fragrance_display_rows = [
        {
            "name": str(row.get("name") or "Fragrance/Essential Oils"),
            "weight": _format_weight(float(row.get("grams") or 0.0), unit_display),
            "percent": _format_percent(float(row.get("pct") or 0.0)),
        }
        for row in fragrance_rows
    ]
    additive_display_rows = [
        {
            "name": str(row.get("name") or "Additive"),
            "weight": _format_weight(float(row.get("grams") or 0.0), unit_display),
            "percent": _format_percent(float(row.get("pct") or 0.0)),
        }
        for row in additive_rows
    ]

    template = _TEMPLATE_ENV.get_template(_PRINT_SHEET_TEMPLATE)
    return template.render(
        generated=generated,
        summary_items=summary_items,
        oil_rows=oil_rows,
        fragrance_rows=fragrance_display_rows,
        additive_rows=additive_display_rows,
        lye_label_display=lye_label_display,
        lye_total_text=lye_total_text,
        water_text=_format_weight(float(result.get("water_g") or 0.0), unit_display),
        assumption_notes=assumption_notes,
    )


__all__ = [
    "build_formula_csv_rows",
    "build_formula_csv_text",
    "build_formula_sheet_html",
]

