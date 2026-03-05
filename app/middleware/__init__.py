"""Request middleware package.

Synopsis:
Provides a thin entrypoint for registering global middleware pipeline hooks.

Glossary:
- Registry: module that wires before/after request handlers.
- Guard: focused request gate that can allow or block.
"""

from .registry import register_middleware

__all__ = ["register_middleware"]
