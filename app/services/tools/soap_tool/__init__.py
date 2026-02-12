"""Soap tool computation package.

Synopsis:
Provides a single orchestration service for soap stage outputs, quality metrics,
additive adjustments, and export-ready formula payloads.

Glossary:
- Soap tool compute: End-to-end calculation bundle for the public soap UI.
"""

from ._core import SoapToolComputationService
from .types import SoapToolComputeRequest

__all__ = [
    "SoapToolComputationService",
    "SoapToolComputeRequest",
]

