"""Data contracts for soap tool calculator service.

Synopsis:
Typed request/response shapes used by the soap calculator service package.

Glossary:
- SAP KOH: Saponification value expressed as mg KOH per gram oil.
- Superfat: Intentional lye discount percentage.
- Water method: One of percent, concentration, or ratio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


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


def _clamp(value: float, minimum: float, maximum: float | None = None) -> float:
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


@dataclass(frozen=True)
class SoapOilInput:
    grams: float
    sap_koh: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapOilInput":
        grams = _clamp(_to_float(payload.get("grams"), 0.0), 0.0)
        sap_koh = _clamp(
            _to_float(payload.get("sap_koh", payload.get("sapKoh")), 0.0),
            0.0,
        )
        return cls(grams=grams, sap_koh=sap_koh)


@dataclass(frozen=True)
class SoapCalculationRequest:
    oils: tuple[SoapOilInput, ...]
    lye_selected: str
    superfat_pct: float
    lye_purity_pct: float
    water_method: str
    water_pct: float
    lye_concentration_pct: float
    water_ratio: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SoapCalculationRequest":
        lye = payload.get("lye")
        water = payload.get("water")
        oils_raw = payload.get("oils")

        lye_data = lye if isinstance(lye, Mapping) else {}
        water_data = water if isinstance(water, Mapping) else {}
        oils_list: Iterable[Mapping[str, Any]] = oils_raw if isinstance(oils_raw, list) else []

        oils = tuple(
            SoapOilInput.from_payload(item)
            for item in oils_list
            if isinstance(item, Mapping)
        )
        lye_selected = _text(lye_data.get("selected", payload.get("lye_selected", "NaOH")), "NaOH")
        water_method = _text(water_data.get("method", payload.get("water_method", "percent")), "percent")
        return cls(
            oils=oils,
            lye_selected=lye_selected,
            superfat_pct=_to_float(lye_data.get("superfat", payload.get("superfat_pct", 5.0)), 5.0),
            lye_purity_pct=_to_float(lye_data.get("purity", payload.get("lye_purity_pct", 100.0)), 100.0),
            water_method=water_method,
            water_pct=_to_float(water_data.get("water_pct", payload.get("water_pct", 33.0)), 33.0),
            lye_concentration_pct=_to_float(
                water_data.get("lye_concentration", payload.get("lye_concentration_pct", 33.0)),
                33.0,
            ),
            water_ratio=_to_float(water_data.get("water_ratio", payload.get("water_ratio", 2.0)), 2.0),
        )


@dataclass(frozen=True)
class SoapCalculationResult:
    total_oils_g: float
    lye_type: str
    lye_selected: str
    superfat_pct: float
    lye_purity_pct: float
    lye_total_g: float
    lye_pure_g: float
    lye_adjusted_g: float
    water_method: str
    water_pct: float
    lye_concentration_input_pct: float
    water_ratio_input: float
    water_g: float
    lye_concentration_pct: float
    water_lye_ratio: float
    sap_avg_koh: float
    used_sap_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_oils_g": self.total_oils_g,
            "lye_type": self.lye_type,
            "lye_selected": self.lye_selected,
            "superfat_pct": self.superfat_pct,
            "lye_purity_pct": self.lye_purity_pct,
            "lye_total_g": self.lye_total_g,
            "lye_pure_g": self.lye_pure_g,
            "lye_adjusted_g": self.lye_adjusted_g,
            "water_method": self.water_method,
            "water_pct": self.water_pct,
            "lye_concentration_input_pct": self.lye_concentration_input_pct,
            "water_ratio_input": self.water_ratio_input,
            "water_g": self.water_g,
            "lye_concentration_pct": self.lye_concentration_pct,
            "water_lye_ratio": self.water_lye_ratio,
            "sap_avg_koh": self.sap_avg_koh,
            "used_sap_fallback": self.used_sap_fallback,
        }


__all__ = [
    "SoapOilInput",
    "SoapCalculationRequest",
    "SoapCalculationResult",
    "_clamp",
]

