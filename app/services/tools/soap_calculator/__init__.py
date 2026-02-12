"""Soap tool calculator package.

Synopsis:
Exports typed request/response contracts and the canonical soap calculator
service used by the public soap formulator route/API.

Glossary:
- Canonical calculator: Authoritative lye/water computation path for the tool.
"""

from .service import SoapToolCalculatorService
from .types import SoapCalculationRequest, SoapCalculationResult, SoapOilInput

__all__ = [
    "SoapToolCalculatorService",
    "SoapCalculationRequest",
    "SoapCalculationResult",
    "SoapOilInput",
]

