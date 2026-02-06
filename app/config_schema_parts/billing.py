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
