"""Config schema: Security and networking settings.

Synopsis:
Defines ProxyFix and security header configuration keys.

Glossary:
- ProxyFix: Werkzeug middleware that trusts proxy headers.
"""

# --- Security fields ---
# Purpose: Provide security and proxy configuration definitions.
FIELDS = [
    {
        "key": "ENABLE_PROXY_FIX",
        "cast": "bool",
        "default": False,
        "description": "Wrap the app in Werkzeug ProxyFix.",
        "required_in": ("staging", "production"),
        "recommended": "true",
    },
    {
        "key": "TRUST_PROXY_HEADERS",
        "cast": "bool",
        "default": True,
        "description": "Legacy proxy header toggle.",
        "recommended": "true",
    },
    {
        "key": "PROXY_FIX_X_FOR",
        "cast": "int",
        "default": 1,
        "description": "Number of X-Forwarded-For headers to trust.",
        "recommended": "1",
    },
    {
        "key": "PROXY_FIX_X_PROTO",
        "cast": "int",
        "default": 1,
        "description": "Number of X-Forwarded-Proto headers to trust.",
        "recommended": "1",
    },
    {
        "key": "PROXY_FIX_X_HOST",
        "cast": "int",
        "default": 1,
        "description": "Number of X-Forwarded-Host headers to trust.",
        "recommended": "1",
    },
    {
        "key": "PROXY_FIX_X_PORT",
        "cast": "int",
        "default": 1,
        "description": "Number of X-Forwarded-Port headers to trust.",
        "recommended": "1",
    },
    {
        "key": "PROXY_FIX_X_PREFIX",
        "cast": "int",
        "default": 0,
        "description": "Number of X-Forwarded-Prefix headers to trust.",
        "recommended": "0",
    },
    {
        "key": "FORCE_SECURITY_HEADERS",
        "cast": "bool",
        "default": True,
        "description": "Force security headers on every response.",
        "recommended": "true",
    },
    {
        "key": "BOT_TRAP_POLICY_PRESET",
        "cast": "str",
        "default": "balanced",
        "description": "Bot trap preset: conservative, balanced, or aggressive.",
        "recommended": "balanced",
        "note": "Preset values are applied unless explicit BOT_TRAP_* numeric overrides are set.",
    },
    {
        "key": "BOT_TRAP_STRIKE_THRESHOLD",
        "cast": "int",
        "default": 3,
        "description": "Suspicious hits required before temporary IP block.",
        "recommended": "3",
        "note": "Optional explicit override for the selected bot trap preset.",
    },
    {
        "key": "BOT_TRAP_STRIKE_WINDOW_SECONDS",
        "cast": "int",
        "default": 600,
        "description": "Rolling strike window in seconds.",
        "recommended": "600",
        "note": "Optional explicit override for the selected bot trap preset.",
    },
    {
        "key": "BOT_TRAP_IP_BLOCK_SECONDS",
        "cast": "int",
        "default": 1800,
        "description": "Base temporary IP block duration in seconds.",
        "recommended": "1800",
        "note": "Optional explicit override for the selected bot trap preset.",
    },
    {
        "key": "BOT_TRAP_IP_BLOCK_MAX_SECONDS",
        "cast": "int",
        "default": 86400,
        "description": "Maximum temporary IP block duration after escalation.",
        "recommended": "86400",
        "note": "Optional explicit override for the selected bot trap preset.",
    },
    {
        "key": "BOT_TRAP_PENALTY_RESET_SECONDS",
        "cast": "int",
        "default": 86400,
        "description": "Seconds before prior penalty level resets for an IP.",
        "recommended": "86400",
        "note": "Optional explicit override for the selected bot trap preset.",
    },
    {
        "key": "BOT_TRAP_ENABLE_PERMANENT_IP_BLOCKS",
        "cast": "bool",
        "default": False,
        "description": "Honor legacy permanent IP block list in bot_traps.json.",
        "recommended": "false",
        "note": "Keep disabled to reduce false positives from recycled/shared IPs.",
    },
    {
        "key": "DISABLE_SECURITY_HEADERS",
        "cast": "bool",
        "default": False,
        "description": "Disable security headers middleware.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
]

# --- Security section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "security",
    "title": "Security & Networking",
    "note": "Enable proxy awareness and security headers behind your load balancer.",
}
