"""Helper utilities for enriching ingredient data from external sources."""
from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_sources"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Environment variable keys
# ---------------------------------------------------------------------------
PUBCHEM_API_KEY = os.getenv("PUBCHEM_API_KEY")
USDA_API_KEY = os.getenv("USDA_API_KEY")
EWG_API_KEY = os.getenv("EWG_API_KEY")
TGSC_API_KEY = os.getenv("TGSC_API_KEY")
NHP_API_KEY = os.getenv("NHP_API_KEY")  # Health Canada natural health products

COSING_CSV_PATH = Path(os.getenv("COSING_CSV_PATH", DATA_DIR / "cosing.csv"))
HSCG_CSV_PATH = Path(os.getenv("HSCG_CSV_PATH", DATA_DIR / "hscg_ingredients.csv"))
TGSC_CSV_PATH = Path(os.getenv("TGSC_CSV_PATH", DATA_DIR / "tgsc_ingredients.csv")).resolve()
NHP_JSON_PATH = Path(os.getenv("NHP_JSON_PATH", DATA_DIR / "health_canada_nhp.json"))

SOURCE_ORDER = [
    "pubchem",
    "cosing",
    "usda",
    "hscg",
    "ewg",
    "tgsc",
    "health_canada_nhp",
]


@dataclass
class SourcePayload:
    source: str
    data: Dict[str, Any]


class IngredientSourceBroker:
    """Attempts to gather structured facts from configured sources."""

    def __init__(self) -> None:
        self.session = requests.Session()

    def _get_json(self, url: str, *, timeout: float = 20) -> Dict[str, Any] | None:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            blob = response.json()
            return blob if isinstance(blob, dict) else None
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("HTTP JSON fetch failed for %s: %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def gather(self, term: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for source_name in SOURCE_ORDER:
            try:
                handler = getattr(self, f"_fetch_{source_name}")
            except AttributeError:
                LOGGER.debug("No handler for source %s", source_name)
                continue
            result = handler(term)
            if not result:
                continue
            payload[source_name] = result.data
        return payload

    # ------------------------------------------------------------------
    # Individual source handlers
    # ------------------------------------------------------------------
    def _fetch_pubchem(self, term: str) -> Optional[SourcePayload]:
        try:
            quoted = requests.utils.quote(term)

            # 1) Resolve name -> CID
            cid_blob = self._get_json(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quoted}/cids/JSON",
                timeout=20,
            )
            cids = (cid_blob or {}).get("IdentifierList", {}).get("CID", [])
            if not cids:
                return None
            cid = cids[0]

            # 2) Pull supported "PropertyTable" properties (PUG REST)
            # Note: properties like Density/BoilingPoint/FlashPoint are *not* valid in the
            # PropertyTable endpoint and must be retrieved via PUG View (not implemented here).
            props_blob = self._get_json(
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
                f"{cid}/property/MolecularFormula,MolecularWeight,ExactMass,IUPACName,InChIKey,CanonicalSMILES/JSON",
                timeout=20,
            )
            props = (props_blob or {}).get("PropertyTable", {}).get("Properties", [])
            if not props:
                return None
            data: Dict[str, Any] = dict(props[0])

            # 3) Pull CAS registry numbers (RN) when available
            rn_blob = self._get_json(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/xrefs/RN/JSON",
                timeout=20,
            )
            infos = (rn_blob or {}).get("InformationList", {}).get("Information", [])
            if infos and isinstance(infos, list) and isinstance(infos[0], dict):
                rns = infos[0].get("RN", [])
                if isinstance(rns, list) and rns:
                    data["cas_numbers"] = rns
                elif isinstance(rns, str) and rns.strip():
                    data["cas_numbers"] = [rns.strip()]

            if PUBCHEM_API_KEY:
                data["api_key_used"] = True

            return SourcePayload(source="pubchem", data=data)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("PubChem lookup failed for %s: %s", term, exc)
            return None

    def _fetch_cosing(self, term: str) -> Optional[SourcePayload]:
        if not COSING_CSV_PATH.exists():
            return None
        term_lower = term.lower()
        try:
            with COSING_CSV_PATH.open(encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    names = [row.get("INCI Name", ""), row.get("Synonyms", "")]
                    if any(term_lower == (name or "").strip().lower() for name in names):
                        return SourcePayload(source="cosing", data=row)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("CosIng CSV lookup failed for %s: %s", term, exc)
        return None

    def _fetch_usda(self, term: str) -> Optional[SourcePayload]:
        api_key = USDA_API_KEY
        if not api_key:
            return None
        try:
            url = "https://api.nal.usda.gov/fdc/v1/foods/search"
            params = {"query": term, "pageSize": 1, "api_key": api_key}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            blob = response.json()
            foods = blob.get("foods", [])
            if not foods:
                return None
            food = foods[0]
            return SourcePayload(source="usda", data=food)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("USDA lookup failed for %s: %s", term, exc)
            return None

    def _fetch_hscg(self, term: str) -> Optional[SourcePayload]:
        if not HSCG_CSV_PATH.exists():
            return None
        term_lower = term.lower()
        try:
            with HSCG_CSV_PATH.open(encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    name = (row.get("Name") or "").strip().lower()
                    if name == term_lower:
                        return SourcePayload(source="hscg", data=row)
        except Exception as exc:
            LOGGER.debug("HSCG CSV lookup failed for %s: %s", term, exc)
        return None

    def _fetch_ewg(self, term: str) -> Optional[SourcePayload]:
        api_key = EWG_API_KEY
        if not api_key:
            return None
        try:
            url = "https://api.ewg.org/skindeep/ingredients"
            params = {"search": term, "api_key": api_key}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            blob = response.json()
            results = blob.get("results") or blob.get("ingredients") or []
            if not results:
                return None
            return SourcePayload(source="ewg", data=results[0])
        except Exception as exc:
            LOGGER.debug("EWG lookup failed for %s: %s", term, exc)
            return None

    def _fetch_tgsc(self, term: str) -> Optional[SourcePayload]:
        if TGSC_API_KEY:
            url = "https://www.thegoodscentscompany.com/api/ingredient"
            try:
                response = self.session.get(url, params={"name": term, "api_key": TGSC_API_KEY}, timeout=10)
                response.raise_for_status()
                blob = response.json()
                if blob:
                    return SourcePayload(source="tgsc", data=blob[0] if isinstance(blob, list) else blob)
            except Exception as exc:
                LOGGER.debug("TGSC API lookup failed for %s: %s", term, exc)
        if TGSC_CSV_PATH.exists():
            try:
                with TGSC_CSV_PATH.open(encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        if (row.get("name") or "").strip().lower() == term.lower():
                            return SourcePayload(source="tgsc", data=row)
            except Exception as exc:
                LOGGER.debug("TGSC CSV lookup failed for %s: %s", term, exc)
        return None

    def _fetch_health_canada_nhp(self, term: str) -> Optional[SourcePayload]:
        if NHP_API_KEY:
            url = "https://health-products.canada.ca/api/natural-ingredient"
            try:
                params = {"lang": "en", "type": "contains", "term": term, "api_key": NHP_API_KEY}
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                blob = response.json()
                if blob:
                    return SourcePayload(source="health_canada_nhp", data=blob[0] if isinstance(blob, list) else blob)
            except Exception as exc:
                LOGGER.debug("Health Canada API lookup failed for %s: %s", term, exc)
        if NHP_JSON_PATH.exists():
            try:
                records: List[Dict[str, Any]] = json.loads(NHP_JSON_PATH.read_text(encoding="utf-8"))
                for record in records:
                    if (record.get("name") or "").strip().lower() == term.lower():
                        return SourcePayload(source="health_canada_nhp", data=record)
            except Exception as exc:
                LOGGER.debug("Health Canada JSON lookup failed for %s: %s", term, exc)
        return None


BROKER = IngredientSourceBroker()


def fetch_metadata(term: str) -> Dict[str, Any]:
    """Convenience wrapper for the rest of the builder."""
    if not term or not term.strip():
        return {}
    result = BROKER.gather(term.strip())
    if result:
        LOGGER.debug("Retrieved external metadata for %s from %s", term, list(result.keys()))
    return result
