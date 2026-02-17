"""Backward-compatible CLI command registration entrypoint.

Synopsis:
Delegates command registration to grouped modules under `app.scripts.commands`.
"""

from .scripts.commands import register_commands

__all__ = ["register_commands"]
