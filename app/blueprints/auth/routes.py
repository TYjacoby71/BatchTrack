"""Backward-compatible auth route exports.

Synopsis:
Re-exports split auth route modules so legacy imports keep working.

Glossary:
- Route export: Import-time forwarding of blueprint handlers from submodules.

Purpose:
Keep historical import paths stable while auth handlers live in focused modules.

Auth routes were split into focused modules to keep concerns isolated:
- login_routes
- oauth_routes
- password_routes
- signup_routes
- verification_routes
- whop_routes
"""

from .login_routes import *  # noqa: F401,F403
from .oauth_routes import *  # noqa: F401,F403
from .password_routes import *  # noqa: F401,F403
from .signup_routes import *  # noqa: F401,F403
from .verification_routes import *  # noqa: F401,F403
from .whop_routes import *  # noqa: F401,F403
