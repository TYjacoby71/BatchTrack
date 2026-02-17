"""Typed contracts for soap tool computation orchestration.

Synopsis:
Normalizes stage payload input into deterministic typed records used by the
soap tool computation package.

Glossary:
- Stage payload: Combined oils, lye/water, additive, and export inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


# --- Float parser ---
# Purpose: Convert loose numeric payload values into safe floats.
# Inputs: Arbitrary value and fallback default.
# Outputs: Parsed float value.
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


# --- Int parser ---
# Purpose: Convert loose payload values into optional integers.
# Inputs: Arbitrary value.
# Outputs: Integer or None when value is empty/invalid.
def _to_int(value: Any) -> int | None:
    try:
        if value in (None, "", []):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Numeric clamp ---
# Purpose: Constrain float values into minimum/maximum bounds.
# Inputs: Candidate float and bounds.
# Outputs: Clamped float.
def _clamp(value: float, minimum: float, maximum: float | None = None) -> float:
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


# --- Text normalizer ---
# Purpose: Normalize arbitrary values into trimmed text.
# Inputs: Arbitrary value and fallback.
# Outputs: Non-empty string.
def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


# --- Fatty profile parser ---
# Purpose: Normalize fatty acid profile mapping values to positive floats.
# Inputs: Arbitrary fatty profile payload.
# Outputs: Sanitized fatty profile dictionary.
def _fatty_profile(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        amount = _clamp(_to_float(value, 0.0), 0.0)
        if amount > 0:
            out[str(key)] = amount
    return out


# --- Soap oil input ---
# Purpose: Represent one normalized oil row from the soap tool.
# Inputs: Oil payload mapping.
# Outputs: Immutable oil input instance.
@dataclass(frozen=True)
class SoapToolOilInput:
    name: str
    grams: float
    sap_koh: float
    iodine: float
    fatty_profile: dict[str, float]
    global_item_id: int | None = None
    default_unit: str | None = None
    ingredient_category_name: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolOilInput":
        return cls(
            name=_text(payload.get("name"), "Oil"),
            grams=_clamp(_to_float(payload.get("grams"), 0.0), 0.0),
            sap_koh=_clamp(
                _to_float(payload.get("sap_koh", payload.get("sapKoh")), 0.0), 0.0
            ),
            iodine=_clamp(_to_float(payload.get("iodine"), 0.0), 0.0),
            fatty_profile=_fatty_profile(
                payload.get("fatty_profile", payload.get("fattyProfile"))
            ),
            global_item_id=_to_int(
                payload.get("global_item_id", payload.get("globalItemId"))
            ),
            default_unit=_text(payload.get("default_unit", payload.get("defaultUnit"))),
            ingredient_category_name=_text(
                payload.get(
                    "ingredient_category_name", payload.get("ingredientCategoryName")
                )
            ),
        )


# --- Soap fragrance input ---
# Purpose: Represent one normalized fragrance row from the soap tool.
# Inputs: Fragrance payload mapping.
# Outputs: Immutable fragrance input instance.
@dataclass(frozen=True)
class SoapToolFragranceInput:
    name: str
    grams: float
    pct: float
    global_item_id: int | None = None
    default_unit: str | None = None
    ingredient_category_name: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolFragranceInput":
        return cls(
            name=_text(payload.get("name"), "Fragrance/Essential Oils"),
            grams=_clamp(_to_float(payload.get("grams"), 0.0), 0.0),
            pct=_clamp(_to_float(payload.get("pct"), 0.0), 0.0, 100.0),
            global_item_id=_to_int(
                payload.get("global_item_id", payload.get("globalItemId"))
            ),
            default_unit=_text(payload.get("default_unit", payload.get("defaultUnit"))),
            ingredient_category_name=_text(
                payload.get(
                    "ingredient_category_name", payload.get("ingredientCategoryName")
                )
            ),
        )


# --- Soap additive input ---
# Purpose: Hold additive percentage and display-name settings from Stage 4/5.
# Inputs: Additive payload mapping.
# Outputs: Immutable additive input instance.
@dataclass(frozen=True)
class SoapToolAdditivesInput:
    lactate_pct: float
    sugar_pct: float
    salt_pct: float
    citric_pct: float
    lactate_name: str
    sugar_name: str
    salt_name: str
    citric_name: str
    lactate_global_item_id: int | None = None
    sugar_global_item_id: int | None = None
    salt_global_item_id: int | None = None
    citric_global_item_id: int | None = None
    lactate_default_unit: str | None = None
    sugar_default_unit: str | None = None
    salt_default_unit: str | None = None
    citric_default_unit: str | None = None
    lactate_category_name: str | None = None
    sugar_category_name: str | None = None
    salt_category_name: str | None = None
    citric_category_name: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolAdditivesInput":
        return cls(
            lactate_pct=_clamp(
                _to_float(payload.get("lactate_pct", payload.get("lactatePct")), 0.0),
                0.0,
                100.0,
            ),
            sugar_pct=_clamp(
                _to_float(payload.get("sugar_pct", payload.get("sugarPct")), 0.0),
                0.0,
                100.0,
            ),
            salt_pct=_clamp(
                _to_float(payload.get("salt_pct", payload.get("saltPct")), 0.0),
                0.0,
                100.0,
            ),
            citric_pct=_clamp(
                _to_float(payload.get("citric_pct", payload.get("citricPct")), 0.0),
                0.0,
                100.0,
            ),
            lactate_name=_text(
                payload.get("lactate_name", payload.get("lactateName")),
                "Sodium Lactate",
            ),
            sugar_name=_text(
                payload.get("sugar_name", payload.get("sugarName")), "Sugar"
            ),
            salt_name=_text(payload.get("salt_name", payload.get("saltName")), "Salt"),
            citric_name=_text(
                payload.get("citric_name", payload.get("citricName")), "Citric Acid"
            ),
            lactate_global_item_id=_to_int(
                payload.get(
                    "lactate_global_item_id", payload.get("lactateGlobalItemId")
                )
            ),
            sugar_global_item_id=_to_int(
                payload.get("sugar_global_item_id", payload.get("sugarGlobalItemId"))
            ),
            salt_global_item_id=_to_int(
                payload.get("salt_global_item_id", payload.get("saltGlobalItemId"))
            ),
            citric_global_item_id=_to_int(
                payload.get("citric_global_item_id", payload.get("citricGlobalItemId"))
            ),
            lactate_default_unit=_text(
                payload.get("lactate_default_unit", payload.get("lactateDefaultUnit"))
            ),
            sugar_default_unit=_text(
                payload.get("sugar_default_unit", payload.get("sugarDefaultUnit"))
            ),
            salt_default_unit=_text(
                payload.get("salt_default_unit", payload.get("saltDefaultUnit"))
            ),
            citric_default_unit=_text(
                payload.get("citric_default_unit", payload.get("citricDefaultUnit"))
            ),
            lactate_category_name=_text(
                payload.get("lactate_category_name", payload.get("lactateCategoryName"))
            ),
            sugar_category_name=_text(
                payload.get("sugar_category_name", payload.get("sugarCategoryName"))
            ),
            salt_category_name=_text(
                payload.get("salt_category_name", payload.get("saltCategoryName"))
            ),
            citric_category_name=_text(
                payload.get("citric_category_name", payload.get("citricCategoryName"))
            ),
        )


# --- Soap lye input ---
# Purpose: Hold lye-selection form values.
# Inputs: Lye payload mapping.
# Outputs: Immutable lye input instance.
@dataclass(frozen=True)
class SoapToolLyeInput:
    selected: str
    superfat: float
    purity: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolLyeInput":
        return cls(
            selected=_text(payload.get("selected"), "NaOH"),
            superfat=_to_float(payload.get("superfat"), 5.0),
            purity=_to_float(payload.get("purity"), 100.0),
        )


# --- Soap water input ---
# Purpose: Hold water-method form values.
# Inputs: Water payload mapping.
# Outputs: Immutable water input instance.
@dataclass(frozen=True)
class SoapToolWaterInput:
    method: str
    water_pct: float
    lye_concentration: float
    water_ratio: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolWaterInput":
        return cls(
            method=_text(payload.get("method"), "percent"),
            water_pct=_to_float(
                payload.get("water_pct", payload.get("waterPct")), 33.0
            ),
            lye_concentration=_to_float(
                payload.get("lye_concentration", payload.get("lyeConcentration")),
                33.0,
            ),
            water_ratio=_to_float(
                payload.get("water_ratio", payload.get("waterRatio")), 2.0
            ),
        )


# --- Soap meta input ---
# Purpose: Carry optional display configuration metadata.
# Inputs: Meta payload mapping.
# Outputs: Immutable meta input instance.
@dataclass(frozen=True)
class SoapToolMetaInput:
    unit_display: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolMetaInput":
        unit = _text(
            payload.get("unit_display", payload.get("unitDisplay")), "g"
        ).lower()
        if unit not in {"g", "oz", "lb"}:
            unit = "g"
        return cls(unit_display=unit)


# --- Soap compute request ---
# Purpose: Aggregate normalized stage inputs for full soap computation.
# Inputs: Raw soap tool payload mapping.
# Outputs: Immutable compute request instance.
@dataclass(frozen=True)
class SoapToolComputeRequest:
    oils: tuple[SoapToolOilInput, ...]
    fragrances: tuple[SoapToolFragranceInput, ...]
    additives: SoapToolAdditivesInput
    lye: SoapToolLyeInput
    water: SoapToolWaterInput
    meta: SoapToolMetaInput

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapToolComputeRequest":
        oils_raw = payload.get("oils")
        fragrances_raw = payload.get("fragrances")
        additives_raw = payload.get("additives")
        lye_raw = payload.get("lye")
        water_raw = payload.get("water")
        meta_raw = payload.get("meta")

        oils_list: Iterable[Mapping[str, Any]] = (
            oils_raw if isinstance(oils_raw, list) else []
        )
        fragrance_list: Iterable[Mapping[str, Any]] = (
            fragrances_raw if isinstance(fragrances_raw, list) else []
        )
        additives_data = additives_raw if isinstance(additives_raw, Mapping) else {}
        lye_data = lye_raw if isinstance(lye_raw, Mapping) else {}
        water_data = water_raw if isinstance(water_raw, Mapping) else {}
        meta_data = meta_raw if isinstance(meta_raw, Mapping) else {}

        return cls(
            oils=tuple(
                SoapToolOilInput.from_payload(item)
                for item in oils_list
                if isinstance(item, Mapping)
            ),
            fragrances=tuple(
                SoapToolFragranceInput.from_payload(item)
                for item in fragrance_list
                if isinstance(item, Mapping)
            ),
            additives=SoapToolAdditivesInput.from_payload(additives_data),
            lye=SoapToolLyeInput.from_payload(lye_data),
            water=SoapToolWaterInput.from_payload(water_data),
            meta=SoapToolMetaInput.from_payload(meta_data),
        )


__all__ = [
    "SoapToolComputeRequest",
    "SoapToolOilInput",
    "SoapToolFragranceInput",
    "SoapToolAdditivesInput",
    "SoapToolLyeInput",
    "SoapToolWaterInput",
    "SoapToolMetaInput",
    "_clamp",
    "_to_float",
]
