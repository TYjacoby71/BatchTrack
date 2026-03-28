"""Integration registry and POS/marketplace helpers.

Synopsis:
Expose integration service-layer modules used by organization and developer routes.

Glossary:
- Connection: Organization-level provider authorization/session state.
- Mapping: Link between BatchTrack SKU metadata and external channel identifiers.
"""

from .connection_service import IntegrationConnectionService
from .registry import build_integration_categories

__all__ = [
    "IntegrationConnectionService",
    "build_integration_categories",
]
