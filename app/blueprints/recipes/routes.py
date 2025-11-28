"""Recipe blueprint route registration.

Routes are now defined in dedicated modules under ``views`` to keep
responsibilities focused. Importing this module ensures that each view file is
loaded and its handlers are registered on ``recipes_bp``.
"""

from .views import ajax_routes as _ajax_routes  # noqa: F401
from .views import create_routes as _create_routes  # noqa: F401
from .views import lineage_routes as _lineage_routes  # noqa: F401
from .views import manage_routes as _manage_routes  # noqa: F401
