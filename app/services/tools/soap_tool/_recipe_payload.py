"""Soap recipe payload assembly service.

Synopsis:
Builds canonical recipe-draft payloads for soap calculations so recipe export
assembly is owned by Python services instead of JavaScript.

Glossary:
- Recipe payload: JSON object consumed by the public draft handoff flow.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping


# --- Soap recipe payload builder ---
# Purpose: Assemble a canonical recipe payload from soap calc + draft context.
# Inputs: Mixed request payload containing calc snapshot, draft lines, and UI context.
# Outputs: Normalized recipe payload dictionary for draft/save workflows.
def build_soap_recipe_payload(payload: dict | None) -> dict:
    incoming = payload if isinstance(payload, Mapping) else {}

    calc_raw = incoming.get("calc")
    calc = calc_raw if isinstance(calc_raw, Mapping) else {}
    context_raw = incoming.get("context")
    context = context_raw if isinstance(context_raw, Mapping) else {}
    lines_raw = incoming.get("draft_lines")
    lines = lines_raw if isinstance(lines_raw, Mapping) else {}

    def as_mapping(value: Any) -> dict:
        return dict(value) if isinstance(value, Mapping) else {}

    def as_list(value: Any) -> list:
        return value if isinstance(value, list) else []

    def text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        normalized = str(value).strip()
        return normalized or default

    def to_float(value: Any, default: float = 0.0) -> float:
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

    def to_int(value: Any) -> int | None:
        try:
            if value in (None, "", []):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def round_to(value: Any, decimals: int) -> float:
        num = to_float(value, 0.0)
        return round(num, decimals)

    def pick(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in mapping:
                return mapping.get(key)
        return default

    def derive_sap_average(oils: list[dict]) -> float:
        weighted = 0.0
        covered = 0.0
        for oil in oils:
            grams = to_float(oil.get("grams"), 0.0)
            sap_koh = to_float(pick(oil, "sapKoh", "sap_koh"), 0.0)
            if grams > 0 and sap_koh > 0:
                weighted += sap_koh * grams
                covered += grams
        return (weighted / covered) if covered > 0 else 0.0

    def normalize_line_rows(items: list[Any], kind: str) -> list[dict]:
        normalized: list[dict] = []
        for raw in items:
            row = as_mapping(raw)
            if not row:
                continue
            name_value = text(row.get("name"))
            global_item_id = to_int(pick(row, "global_item_id", "globalItemId"))
            quantity = to_float(row.get("quantity"), 0.0)
            if kind == "container":
                entry: dict[str, Any] = {
                    "quantity": int(quantity) if quantity > 0 else 1
                }
            else:
                entry = {
                    "quantity": float(quantity) if quantity >= 0 else 0.0,
                    "unit": text(row.get("unit"), "gram"),
                }
            if name_value:
                entry["name"] = name_value
            if global_item_id is not None:
                entry["global_item_id"] = global_item_id
            normalized.append(entry)
        return normalized

    oils_raw = as_list(calc.get("oils"))
    oils_for_notes: list[dict] = []
    base_ingredients: list[dict] = []
    for raw_oil in oils_raw:
        oil = as_mapping(raw_oil)
        if not oil:
            continue
        grams = to_float(oil.get("grams"), 0.0)
        oil_name = text(oil.get("name")) or None
        sap_koh = to_float(pick(oil, "sap_koh", "sapKoh"), 0.0)
        iodine = to_float(oil.get("iodine"), 0.0)
        fatty_profile = pick(oil, "fatty_profile", "fattyProfile") or None
        global_item_id = to_int(pick(oil, "global_item_id", "globalItemId"))
        default_unit = text(pick(oil, "default_unit", "defaultUnit")) or None
        ingredient_category_name = (
            text(pick(oil, "ingredient_category_name", "ingredientCategoryName"))
            or None
        )

        oil_note = {
            "name": oil_name,
            "grams": round_to(grams, 2),
            "iodine": iodine if iodine > 0 else None,
            "sap_koh": sap_koh if sap_koh > 0 else None,
            "fatty_profile": fatty_profile,
            "global_item_id": global_item_id,
            "default_unit": default_unit,
            "ingredient_category_name": ingredient_category_name,
        }
        oils_for_notes.append(oil_note)

        if grams > 0:
            ingredient_entry = {
                "quantity": round_to(grams, 2),
                "unit": "gram",
            }
            if oil_name:
                ingredient_entry["name"] = oil_name
            if global_item_id is not None:
                ingredient_entry["global_item_id"] = global_item_id
            if default_unit:
                ingredient_entry["default_unit"] = default_unit
            if ingredient_category_name:
                ingredient_entry["ingredient_category_name"] = ingredient_category_name
            base_ingredients.append(ingredient_entry)

    lye_type = text(calc.get("lyeType"), "NaOH")
    lye_adjusted = to_float(calc.get("lyeAdjusted"), 0.0)
    water_g = to_float(calc.get("water"), 0.0)
    if lye_adjusted > 0:
        lye_name = (
            "Potassium Hydroxide (KOH)"
            if lye_type == "KOH"
            else "Sodium Hydroxide (NaOH)"
        )
        base_ingredients.append(
            {"name": lye_name, "quantity": round_to(lye_adjusted, 2), "unit": "gram"}
        )
    if water_g > 0:
        base_ingredients.append(
            {
                "name": "Distilled Water",
                "quantity": round_to(water_g, 2),
                "unit": "gram",
            }
        )

    additives = as_mapping(calc.get("additives"))
    fragrances_raw = as_list(calc.get("fragrances"))
    if not fragrances_raw:
        fragrances_raw = as_list(additives.get("fragranceRows"))
    for raw_fragrance in fragrances_raw:
        row = as_mapping(raw_fragrance)
        if not row:
            continue
        grams = to_float(row.get("grams"), 0.0)
        if grams <= 0:
            continue
        ingredient_entry = {
            "name": text(row.get("name"), "Fragrance/Essential Oils"),
            "quantity": round_to(grams, 2),
            "unit": "gram",
        }
        row_global_item_id = to_int(pick(row, "global_item_id", "globalItemId"))
        row_default_unit = text(pick(row, "default_unit", "defaultUnit")) or None
        row_category = (
            text(
                pick(
                    row,
                    "ingredient_category_name",
                    "ingredientCategoryName",
                    "categoryName",
                )
            )
            or None
        )
        if row_global_item_id is not None:
            ingredient_entry["global_item_id"] = row_global_item_id
        if row_default_unit:
            ingredient_entry["default_unit"] = row_default_unit
        if row_category:
            ingredient_entry["ingredient_category_name"] = row_category
        base_ingredients.append(ingredient_entry)

    additive_name_defaults = {
        "lactate": "Sodium Lactate",
        "sugar": "Sugar",
        "salt": "Salt",
        "citric": "Citric Acid",
    }
    additive_defs = (
        ("lactate", "lactateG"),
        ("sugar", "sugarG"),
        ("salt", "saltG"),
        ("citric", "citricG"),
    )
    for prefix, grams_key in additive_defs:
        grams = to_float(additives.get(grams_key), 0.0)
        if grams <= 0:
            continue
        entry = {
            "name": text(
                pick(additives, f"{prefix}Name", f"{prefix}_name"),
                additive_name_defaults[prefix],
            ),
            "quantity": round_to(grams, 2),
            "unit": "gram",
        }
        additive_gi = to_int(
            pick(
                additives,
                f"{prefix}GlobalItemId",
                f"{prefix}_global_item_id",
            )
        )
        additive_default_unit = (
            text(pick(additives, f"{prefix}DefaultUnit", f"{prefix}_default_unit"))
            or None
        )
        additive_category = (
            text(
                pick(
                    additives,
                    f"{prefix}CategoryName",
                    f"{prefix}_ingredient_category_name",
                    f"{prefix}_category_name",
                )
            )
            or None
        )
        if additive_gi is not None:
            entry["global_item_id"] = additive_gi
        if additive_default_unit:
            entry["default_unit"] = additive_default_unit
        if additive_category:
            entry["ingredient_category_name"] = additive_category
        base_ingredients.append(entry)

    citric_lye_g = to_float(additives.get("citricLyeG"), 0.0)
    if citric_lye_g > 0:
        base_ingredients.append(
            {
                "name": "Extra Lye for Citric Acid",
                "quantity": round_to(citric_lye_g, 2),
                "unit": "gram",
            }
        )

    quality_report = as_mapping(calc.get("qualityReport"))
    if not quality_report:
        quality_report = as_mapping(calc.get("quality_report"))
    fatty_percent = as_mapping(quality_report.get("fatty_acids_pct"))
    qualities = as_mapping(quality_report.get("qualities"))

    sap_avg = to_float(calc.get("sapAvg"), 0.0)
    if sap_avg <= 0:
        sap_avg = to_float(quality_report.get("sap_avg_koh"), 0.0)
    if sap_avg <= 0:
        sap_avg = derive_sap_average(oils_for_notes)
    iodine = to_float(quality_report.get("iodine"), 0.0)
    ins = to_float(quality_report.get("ins"), 0.0)
    if ins <= 0 and sap_avg > 0 and iodine > 0:
        ins = sap_avg - iodine

    mold_raw = as_mapping(context.get("mold"))
    mold_payload = {
        "waterWeight": to_float(pick(mold_raw, "waterWeight", "water_weight"), 0.0),
        "oilPct": to_float(pick(mold_raw, "oilPct", "oil_pct"), 0.0),
        "shape": text(mold_raw.get("shape"), "loaf"),
        "useCylinder": bool(
            pick(mold_raw, "useCylinder", "use_cylinder", default=False)
        ),
        "cylinderFactor": to_float(
            pick(mold_raw, "cylinderFactor", "cylinder_factor"), 0.0
        ),
        "effectiveCapacity": to_float(
            pick(mold_raw, "effectiveCapacity", "effective_capacity"), 0.0
        ),
        "targetOils": to_float(pick(mold_raw, "targetOils", "target_oils"), 0.0),
    }

    quality_focus = context.get("quality_focus")
    if not isinstance(quality_focus, list):
        quality_focus = []

    total_oils = to_float(calc.get("totalOils"), 0.0)
    batch_yield = to_float(calc.get("batchYield"), 0.0)
    lye_pure = to_float(calc.get("lyePure"), 0.0)

    notes_blob = {
        "source": text(context.get("source"), "soap_tool"),
        "schema_version": int(to_float(context.get("schema_version"), 1.0)),
        "unit_display": text(context.get("unit_display"), "g"),
        "input_mode": text(context.get("input_mode"), "mixed"),
        "quality_preset": text(context.get("quality_preset"), "balanced"),
        "quality_focus": [text(item) for item in quality_focus if text(item)],
        "mold": mold_payload,
        "oils": oils_for_notes,
        "totals": {
            "total_oils_g": round_to(total_oils, 2),
            "batch_yield_g": round_to(batch_yield, 2),
            "lye_pure_g": round_to(lye_pure, 2),
            "lye_adjusted_g": round_to(lye_adjusted, 2),
            "water_g": round_to(water_g, 2),
        },
        "lye": {
            "lye_type": lye_type,
            "superfat": to_float(calc.get("superfat"), 0.0),
            "purity": to_float(calc.get("purity"), 0.0),
            "water_method": text(calc.get("waterMethod"), "percent"),
            "water_pct": to_float(calc.get("waterPct"), 0.0),
            "lye_concentration": to_float(calc.get("lyeConcentration"), 0.0),
            "water_ratio": to_float(calc.get("waterRatio"), 0.0),
        },
        "additives": {
            "fragrance_pct": to_float(additives.get("fragrancePct"), 0.0),
            "lactate_pct": to_float(additives.get("lactatePct"), 0.0),
            "sugar_pct": to_float(additives.get("sugarPct"), 0.0),
            "salt_pct": to_float(additives.get("saltPct"), 0.0),
            "citric_pct": to_float(additives.get("citricPct"), 0.0),
            "fragrance_g": round_to(additives.get("fragranceG"), 2),
            "lactate_g": round_to(additives.get("lactateG"), 2),
            "sugar_g": round_to(additives.get("sugarG"), 2),
            "salt_g": round_to(additives.get("saltG"), 2),
            "citric_g": round_to(additives.get("citricG"), 2),
            "citric_lye_g": round_to(additives.get("citricLyeG"), 2),
        },
        "qualities": {
            "hardness": round_to(qualities.get("hardness"), 1),
            "cleansing": round_to(qualities.get("cleansing"), 1),
            "conditioning": round_to(qualities.get("conditioning"), 1),
            "bubbly": round_to(qualities.get("bubbly"), 1),
            "creamy": round_to(qualities.get("creamy"), 1),
            "iodine": round_to(iodine, 1),
            "ins": round_to(ins, 1),
            "sap_avg": round_to(sap_avg, 1),
        },
        "fatty_acids": fatty_percent,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    custom_ingredients = normalize_line_rows(
        as_list(lines.get("ingredients")), "ingredient"
    )
    custom_consumables = normalize_line_rows(
        as_list(lines.get("consumables")), "consumable"
    )
    custom_containers = normalize_line_rows(
        as_list(lines.get("containers")), "container"
    )

    return {
        "name": "Soap (Draft)",
        "instructions": "Draft from Soap Tools",
        "predicted_yield": round_to(batch_yield, 2),
        "predicted_yield_unit": "gram",
        "category_name": "Soaps",
        "category_data": {
            "soap_superfat": to_float(calc.get("superfat"), 0.0),
            "soap_lye_type": lye_type,
            "soap_lye_purity": to_float(calc.get("purity"), 0.0),
            "soap_water_method": text(calc.get("waterMethod"), "percent"),
            "soap_water_pct": to_float(calc.get("waterPct"), 0.0),
            "soap_lye_concentration": to_float(calc.get("lyeConcentration"), 0.0),
            "soap_water_ratio": to_float(calc.get("waterRatio"), 0.0),
            "soap_oils_total_g": total_oils,
            "soap_lye_g": lye_adjusted,
            "soap_water_g": water_g,
        },
        "ingredients": base_ingredients + custom_ingredients,
        "consumables": custom_consumables,
        "containers": custom_containers,
        "notes": json.dumps(notes_blob),
    }


__all__ = ["build_soap_recipe_payload"]
