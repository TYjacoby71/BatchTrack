"""Backward-compatible shim for old `app.utils.authorization` imports."""

from __future__ import annotations

import warnings

from .permissions import *  # noqa: F401,F403

warnings.warn(
    "`app.utils.authorization` is deprecated; import from `app.utils.permissions` instead.",
    DeprecationWarning,
    stacklevel=2,
)
