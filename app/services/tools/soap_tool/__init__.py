"""Soap tool computation package.

Synopsis:
Provides a single orchestration service for soap stage outputs, quality metrics,
additive adjustments, and export-ready formula payloads.

Glossary:
- Soap tool compute: End-to-end calculation bundle for the public soap UI.
"""

from ._core import SoapToolComputationService
from ._catalog import get_bulk_catalog_page
from ._lye_water import compute_lye_water_values
from ._policy import get_soap_tool_policy
from ._recipe_payload import build_soap_recipe_payload
from .types import SoapToolComputeRequest

__all__ = [
    "SoapToolComputationService",
    "SoapToolComputeRequest",
    "compute_lye_water_values",
    "get_bulk_catalog_page",
    "get_soap_tool_policy",
    "build_soap_recipe_payload",
]

