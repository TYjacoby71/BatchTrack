"""Config schema: Email settings.

Synopsis:
Defines email provider and SMTP configuration keys.

Glossary:
- Provider: Email delivery backend (SMTP, SendGrid, Postmark).
"""

# --- Email fields ---
# Purpose: Provide email configuration definitions.
FIELDS = [
    {
        "key": "EMAIL_PROVIDER",
        "cast": "str",
        "default": "smtp",
        "description": "Email provider selector.",
        "recommended": "smtp",
    },
    {
        "key": "MAIL_SERVER",
        "cast": "str",
        "default": "smtp.gmail.com",
        "description": "SMTP server hostname.",
        "recommended": "smtp.your-provider.com",
    },
    {
        "key": "MAIL_PORT",
        "cast": "int",
        "default": 587,
        "description": "SMTP server port.",
        "recommended": "587",
    },
    {
        "key": "MAIL_USE_TLS",
        "cast": "bool",
        "default": True,
        "description": "Enable TLS for SMTP.",
        "recommended": "true",
    },
    {
        "key": "MAIL_USE_SSL",
        "cast": "bool",
        "default": False,
        "description": "Enable SSL for SMTP.",
        "recommended": "false",
    },
    {
        "key": "MAIL_USERNAME",
        "cast": "str",
        "default": None,
        "description": "SMTP username.",
        "secret": True,
    },
    {
        "key": "MAIL_PASSWORD",
        "cast": "str",
        "default": None,
        "description": "SMTP password.",
        "secret": True,
    },
    {
        "key": "MAIL_DEFAULT_SENDER",
        "cast": "str",
        "default": "noreply@batchtrack.app",
        "description": "Default email sender address.",
        "recommended": "noreply@batchtrack.app",
    },
    {
        "key": "SENDGRID_API_KEY",
        "cast": "str",
        "default": None,
        "description": "SendGrid API key.",
        "secret": True,
    },
    {
        "key": "POSTMARK_SERVER_TOKEN",
        "cast": "str",
        "default": None,
        "description": "Postmark server token.",
        "secret": True,
    },
    {
        "key": "MAILGUN_API_KEY",
        "cast": "str",
        "default": None,
        "description": "Mailgun API key.",
        "secret": True,
    },
    {
        "key": "MAILGUN_DOMAIN",
        "cast": "str",
        "default": None,
        "description": "Mailgun domain.",
    },
]

# --- Email section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "email",
    "title": "Email & Notifications",
    "note": "Configure exactly one provider for transactional email.",
}
