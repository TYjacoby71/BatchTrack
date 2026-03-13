"""Config schema: Operations settings.

Synopsis:
Defines operational webhook and integration endpoints.

Glossary:
- Operations: Runtime integrations for events and maintenance.
"""

# --- Operations fields ---
# Purpose: Provide operational integration configuration definitions.
FIELDS = [
    {
        "key": "DOMAIN_EVENT_WEBHOOK_URL",
        "cast": "str",
        "default": None,
        "description": "Outbound webhook URL for domain events.",
        "recommended": "https://your-domain-event-endpoint.example",
    },
    {
        "key": "GOOGLE_ANALYTICS_MEASUREMENT_ID",
        "cast": "str",
        "default": None,
        "description": "GA4 measurement id for website traffic analytics.",
        "recommended": "G-XXXXXXXXXX",
    },
    {
        "key": "GOOGLE_ADS_CONVERSION_ID",
        "cast": "str",
        "default": None,
        "description": "Google Ads conversion id used for direct conversion tags (AW-XXXXXXXXXX).",
        "recommended": "AW-XXXXXXXXXX",
    },
    {
        "key": "GOOGLE_ADS_PURCHASE_CONVERSION_LABEL",
        "cast": "str",
        "default": None,
        "description": "Google Ads purchase conversion label paired with GOOGLE_ADS_CONVERSION_ID.",
        "recommended": "your_purchase_conversion_label",
    },
    {
        "key": "POSTHOG_PROJECT_API_KEY",
        "cast": "str",
        "default": None,
        "description": "PostHog project API key for product and traffic analytics.",
        "secret": True,
    },
    {
        "key": "POSTHOG_HOST",
        "cast": "str",
        "default": "https://us.i.posthog.com",
        "description": "PostHog ingestion host (cloud region or self-hosted URL).",
        "recommended": "https://us.i.posthog.com",
    },
    {
        "key": "POSTHOG_CAPTURE_PAGEVIEW",
        "cast": "bool",
        "default": True,
        "description": "Enable automatic PostHog pageview tracking.",
        "recommended": "true",
    },
    {
        "key": "POSTHOG_CAPTURE_PAGELEAVE",
        "cast": "bool",
        "default": True,
        "description": "Enable automatic PostHog pageleave tracking.",
        "recommended": "true",
    },
]

# --- Operations section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "operations",
    "title": "Operations & Webhooks",
    "note": "Optional operational integrations and webhook destinations.",
}
