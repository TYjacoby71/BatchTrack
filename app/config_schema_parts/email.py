"""Config schema: Email settings.

Synopsis:
Defines email provider, SMTP, and account email-security configuration keys.

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
    {
        "key": "EMAIL_SMTP_ALLOW_NO_AUTH",
        "cast": "bool",
        "default": False,
        "description": "Allow SMTP mode without MAIL_USERNAME/MAIL_PASSWORD.",
        "recommended": "false",
        "note": "Keep false unless your SMTP relay allows trusted unauthenticated senders.",
    },
    {
        "key": "AUTH_EMAIL_VERIFICATION_MODE",
        "cast": "str",
        "default": "prompt",
        "description": "Email verification mode: off, prompt, or required.",
        "recommended": "prompt",
        "note": "prompt = allow login but show verification prompts; required = block login until verified.",
    },
    {
        "key": "AUTH_EMAIL_REQUIRE_PROVIDER",
        "cast": "bool",
        "default": True,
        "description": "Disable email auth flows when provider credentials are unavailable.",
        "recommended": "true",
    },
    {
        "key": "AUTH_PASSWORD_RESET_ENABLED",
        "cast": "bool",
        "default": True,
        "description": "Enable forgot/reset password email token flow.",
        "recommended": "true",
    },
    {
        "key": "EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS",
        "cast": "int",
        "default": 24,
        "description": "Verification token lifetime in hours.",
        "recommended": "24",
    },
    {
        "key": "PASSWORD_RESET_TOKEN_EXPIRY_HOURS",
        "cast": "int",
        "default": 24,
        "description": "Password reset token lifetime in hours.",
        "recommended": "24",
    },
]

# --- Email section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "email",
    "title": "Email & Notifications",
    "note": "Configure exactly one provider for transactional email and account security flows.",
}
