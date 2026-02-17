"""Tier presentation package exports.

Synopsis:
Exposes the core orchestrator used to build tier comparison and single-tier
presentation payloads from catalog rules.

Glossary:
- Tier presentation core: Primary coordinator for feature-row evaluation.
"""

from .core import TierPresentationCore

__all__ = ["TierPresentationCore"]
