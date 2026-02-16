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
from ._print_policy import get_print_policy
from ._sheet import build_normalized_print_sheet_payload
from .types import SoapToolComputeRequest

__all__ = [
    "SoapToolComputationService",
    "SoapToolComputeRequest",
    "compute_lye_water_values",
    "get_bulk_catalog_page",
    "get_print_policy",
    "build_normalized_print_sheet_payload",
]

