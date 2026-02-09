"""Config schema: Billing settings.

Synopsis:
Defines Stripe credentials and billing cache configuration keys.

Glossary:
- Stripe: Payment processor used for subscriptions and add-ons.
"""

# --- Billing fields ---
# Purpose: Provide billing and Stripe configuration definitions.
FIELDS = [
    {
        "key": "STRIPE_PUBLISHABLE_KEY",
        "cast": "str",
        "default": None,
        "description": "Stripe publishable key.",
        "secret": True,
    },
    {
        "key": "STRIPE_SECRET_KEY",
        "cast": "str",
        "default": None,
        "description": "Stripe secret key.",
        "secret": True,
    },
    {
        "key": "STRIPE_WEBHOOK_SECRET",
        "cast": "str",
        "default": None,
        "description": "Stripe webhook secret.",
        "secret": True,
    },
    {
        "key": "LIFETIME_YEARLY_LOOKUP_KEYS",
        "cast": "str",
        "default": "",
        "description": "Lifetime yearly lookup-key map (JSON or key:value CSV).",
        "note": "Example: hobbyist:batchtrack_solo_yearly,enthusiast:batchtrack_team_yearly,fanatic:batchtrack_enterprise_yearly",
    },
    {
        "key": "LIFETIME_COUPON_CODES",
        "cast": "str",
        "default": "",
        "description": "Lifetime coupon code map for seat counters (JSON or key:value CSV).",
        "note": "Example: hobbyist:LIFETIME-HOBBYIST,enthusiast:LIFETIME-ENTHUSIAST,fanatic:LIFETIME-FANATIC",
    },
    {
        "key": "LIFETIME_COUPON_IDS",
        "cast": "str",
        "default": "",
        "description": "Optional Stripe coupon-id map to auto-apply discounts (JSON or key:value CSV).",
    },
    {
        "key": "LIFETIME_PROMOTION_CODE_IDS",
        "cast": "str",
        "default": "",
        "description": "Optional Stripe promotion-code-id map to auto-apply discounts (JSON or key:value CSV).",
    },
    {
        "key": "STANDARD_YEARLY_LOOKUP_KEYS",
        "cast": "str",
        "default": "",
        "description": "Standard yearly lookup-key map (JSON or key:value CSV).",
        "note": "Use when monthly->yearly key naming is non-standard.",
    },
    {
        "key": "BILLING_CACHE_ENABLED",
        "cast": "bool",
        "default": True,
        "description": "Enable billing cache.",
        "recommended": "true",
    },
    {
        "key": "BILLING_GATE_CACHE_TTL_SECONDS",
        "cast": "int",
        "default": 60,
        "description": "Billing cache TTL in seconds.",
        "recommended": "60",
    },
    {
        "key": "BILLING_STATUS_CACHE_TTL",
        "cast": "int",
        "default": 120,
        "description": "Billing status cache TTL in seconds.",
        "recommended": "120",
    },
]

# --- Billing section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "billing",
    "title": "Billing & Payments",
    "note": "Stripe credentials and billing cache settings.",
}
