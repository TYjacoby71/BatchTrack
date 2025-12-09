"""Constants shared across recipe service modules."""

from decimal import Decimal

_ALLOWED_RECIPE_STATUSES = {'draft', 'published'}
_UNSET = object()
_CENTS = Decimal("0.01")

__all__ = [
    "_ALLOWED_RECIPE_STATUSES",
    "_UNSET",
    "_CENTS",
]
