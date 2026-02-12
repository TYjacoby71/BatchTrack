"""Soap formula sheet and CSV builders.

Synopsis:
Builds export-ready CSV rows/text and printable HTML from computed soap tool
result payloads in a single backend authority.

Glossary:
- Formula sheet: Human-readable print view of recipe outputs.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

UNIT_FACTORS = {
    "g": 1.0,
    "oz": 28.3495,
    "lb": 453.592,
}


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


# --- CSV rows builder ---
# Purpose: Build canonical soap formula CSV row matrix.
# Inputs: Computed soap result dictionary and unit display.
# Outputs: List of CSV rows.
def build_formula_csv_rows(result: dict, unit_display: str) -> list[list[str | float]]:
    total_oils = float(result.get("total_oils_g") or 0.0)
    additives = result.get("additives") or {}
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

    lye_adjusted = float(result.get("lye_adjusted_g") or 0.0)
    if lye_adjusted > 0:
        lye_name = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
        rows.append(["Lye", lye_name, round(_from_grams(lye_adjusted, unit_display), 2), unit_display, ""])

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

    if float(additives.get("citricLyeG") or 0.0) > 0:
        rows.append(
            [
                "Additives",
                "Extra Lye for Citric Acid",
                round(_from_grams(float(additives.get("citricLyeG") or 0.0), unit_display), 2),
                unit_display,
                "",
            ]
        )
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

    oil_rows_html = "".join(
        f"<tr><td>{escape(str(oil.get('name') or 'Oil'))}</td>"
        f"<td class='text-end'>{_format_weight(float(oil.get('grams') or 0.0), unit_display)}</td>"
        f"<td class='text-end'>{_format_percent(((float(oil.get('grams') or 0.0) / total_oils) * 100.0) if total_oils > 0 else 0.0)}</td></tr>"
        for oil in oils
    ) or "<tr><td colspan='3' class='text-muted'>No oils added.</td></tr>"

    fragrance_rows_html = "".join(
        f"<tr><td>{escape(str(row.get('name') or 'Fragrance/Essential Oils'))}</td>"
        f"<td class='text-end'>{_format_weight(float(row.get('grams') or 0.0), unit_display)}</td>"
        f"<td class='text-end'>{_format_percent(float(row.get('pct') or 0.0))}</td></tr>"
        for row in fragrance_rows
    ) or "<tr><td colspan='3' class='text-muted'>No fragrances added.</td></tr>"

    additive_rows_html = "".join(
        f"<tr><td>{escape(str(row['name']))}</td>"
        f"<td class='text-end'>{_format_weight(float(row['grams']), unit_display)}</td>"
        f"<td class='text-end'>{_format_percent(float(row['pct']))}</td></tr>"
        for row in additive_rows
    ) or "<tr><td colspan='3' class='text-muted'>No additives added.</td></tr>"

    lye_label = "Potassium Hydroxide (KOH)" if result.get("lye_type") == "KOH" else "Sodium Hydroxide (NaOH)"
    extra_lye = float(additives.get("citricLyeG") or 0.0)
    extra_lye_row = (
        f"<tr><td>Extra Lye for Citric Acid</td><td class='text-end'>{_format_weight(extra_lye, unit_display)}</td></tr>"
        if extra_lye > 0
        else ""
    )
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    batch_yield = float((result.get("results_card") or {}).get("batch_yield_g") or 0.0)

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Soap Formula Sheet</title>
    <style>
      body {{ font-family: Arial, sans-serif; color: #111; margin: 24px; }}
      h1 {{ font-size: 20px; margin-bottom: 4px; }}
      h2 {{ font-size: 16px; margin-top: 20px; }}
      .meta {{ font-size: 12px; color: #555; margin-bottom: 12px; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
      th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }}
      th {{ background: #f3f4f6; text-align: left; }}
      .text-end {{ text-align: right; }}
      .summary-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 16px; font-size: 12px; }}
      .summary-item {{ display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 4px 0; }}
      .text-muted {{ color: #666; }}
    </style>
  </head>
  <body>
    <h1>Soap Formula Sheet</h1>
    <div class="meta">Generated {generated}</div>
    <div class="summary-grid">
      <div class="summary-item"><span>Lye type</span><span>{escape(str(result.get("lye_type") or "--"))}</span></div>
      <div class="summary-item"><span>Superfat</span><span>{_format_percent(float(result.get("superfat_pct") or 0.0))}</span></div>
      <div class="summary-item"><span>Lye purity</span><span>{_format_percent(float(result.get("lye_purity_pct") or 0.0))}</span></div>
      <div class="summary-item"><span>Total oils</span><span>{_format_weight(total_oils, unit_display)}</span></div>
      <div class="summary-item"><span>Water</span><span>{_format_weight(float(result.get("water_g") or 0.0), unit_display)}</span></div>
      <div class="summary-item"><span>Batch yield</span><span>{_format_weight(batch_yield, unit_display)}</span></div>
      <div class="summary-item"><span>Water method</span><span>{escape(str(result.get("water_method") or "--"))}</span></div>
      <div class="summary-item"><span>Lye concentration</span><span>{_format_percent(float(result.get("lye_concentration_pct") or 0.0))}</span></div>
    </div>

    <h2>Oils</h2>
    <table>
      <thead><tr><th>Oil</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr></thead>
      <tbody>{oil_rows_html}</tbody>
    </table>

    <h2>Lye & Water</h2>
    <table>
      <thead><tr><th>Item</th><th class="text-end">Weight</th></tr></thead>
      <tbody>
        <tr><td>{lye_label}</td><td class="text-end">{_format_weight(float(result.get("lye_adjusted_g") or 0.0), unit_display)}</td></tr>
        <tr><td>Distilled Water</td><td class="text-end">{_format_weight(float(result.get("water_g") or 0.0), unit_display)}</td></tr>
        {extra_lye_row}
      </tbody>
    </table>

    <h2>Fragrance & Essential Oils</h2>
    <table>
      <thead><tr><th>Fragrance</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr></thead>
      <tbody>{fragrance_rows_html}</tbody>
    </table>

    <h2>Additives</h2>
    <table>
      <thead><tr><th>Additive</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr></thead>
      <tbody>{additive_rows_html}</tbody>
    </table>
  </body>
</html>"""


__all__ = [
    "build_formula_csv_rows",
    "build_formula_csv_text",
    "build_formula_sheet_html",
]

