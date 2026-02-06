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
]

# --- Operations section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "operations",
    "title": "Operations & Webhooks",
    "note": "Optional operational integrations and webhook destinations.",
}
