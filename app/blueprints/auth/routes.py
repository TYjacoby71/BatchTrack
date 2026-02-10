"""Backward-compatible auth route exports.

Auth routes were split into focused modules to keep concerns isolated:
- login_routes
- oauth_routes
- signup_routes
- verification_routes
- whop_routes
"""

from .login_routes import *  # noqa: F401,F403
from .oauth_routes import *  # noqa: F401,F403
from .signup_routes import *  # noqa: F401,F403
from .verification_routes import *  # noqa: F401,F403
from .whop_routes import *  # noqa: F401,F403
