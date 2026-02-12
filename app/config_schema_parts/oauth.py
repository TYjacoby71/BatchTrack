"""Config schema: OAuth and marketplace settings.

Synopsis:
Defines OAuth and marketplace integration credentials.

Glossary:
- OAuth: Authentication protocol for third-party login providers.
"""

# --- OAuth fields ---
# Purpose: Provide OAuth and marketplace configuration definitions.
FIELDS = [
    {
        "key": "GOOGLE_OAUTH_CLIENT_ID",
        "cast": "str",
        "default": None,
        "description": "Google OAuth 2.0 client ID.",
        "secret": True,
    },
    {
        "key": "GOOGLE_OAUTH_CLIENT_SECRET",
        "cast": "str",
        "default": None,
        "description": "Google OAuth 2.0 client secret.",
        "secret": True,
    },
    {
        "key": "FACEBOOK_OAUTH_APP_ID",
        "cast": "str",
        "default": None,
        "description": "Facebook OAuth app ID.",
        "secret": True,
    },
    {
        "key": "FACEBOOK_OAUTH_APP_SECRET",
        "cast": "str",
        "default": None,
        "description": "Facebook OAuth app secret.",
        "secret": True,
    },
    {
        "key": "WHOP_API_KEY",
        "cast": "str",
        "default": None,
        "description": "Whop API key.",
        "secret": True,
    },
    {
        "key": "WHOP_APP_ID",
        "cast": "str",
        "default": None,
        "description": "Whop app ID.",
        "secret": True,
    },
]

# --- OAuth section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "oauth",
    "title": "OAuth & Marketplace",
    "note": "Optional integrations for SSO and marketplace licensing.",
}
