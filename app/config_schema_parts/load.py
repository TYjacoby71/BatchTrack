"""Config schema: Load testing settings.

Synopsis:
Defines Locust configuration knobs used in loadtests.

Glossary:
- Locust: Load testing tool used to simulate user traffic.
"""

# --- Load test fields ---
# Purpose: Provide load testing configuration definitions.
FIELDS = [
    {
        "key": "LOCUST_USER_BASE",
        "cast": "str",
        "default": "loadtest_user",
        "description": "Username prefix for generated test accounts.",
        "recommended": "loadtest_user",
    },
    {
        "key": "LOCUST_USER_PASSWORD",
        "cast": "str",
        "default": "loadtest123",
        "description": "Password shared by generated load-test users.",
        "recommended": "loadtest123",
        "secret": True,
    },
    {
        "key": "LOCUST_USER_COUNT",
        "cast": "int",
        "default": 10000,
        "description": "Number of sequential users to generate.",
        "recommended": "500",
    },
    {
        "key": "LOCUST_CACHE_TTL",
        "cast": "int",
        "default": 120,
        "description": "Seconds before Locust refreshes cached IDs.",
        "recommended": "120",
    },
    {
        "key": "LOCUST_REQUIRE_HTTPS",
        "cast": "bool",
        "default": True,
        "description": "Require HTTPS host for Locust logins.",
        "recommended": "1",
    },
    {
        "key": "LOCUST_LOG_LOGIN_FAILURE_CONTEXT",
        "cast": "bool",
        "default": False,
        "description": "Log structured auth.login failures.",
        "recommended": "0",
    },
    {
        "key": "LOCUST_ENABLE_BROWSE_USERS",
        "cast": "bool",
        "default": True,
        "description": "Enable anonymous browse users in Locust.",
        "recommended": "1",
    },
    {
        "key": "LOCUST_FAIL_FAST_LOGIN",
        "cast": "bool",
        "default": True,
        "description": "Abort user if login fails during Locust start.",
        "recommended": "1",
    },
    {
        "key": "LOCUST_ABORT_ON_AUTH_FAILURE",
        "cast": "bool",
        "default": False,
        "description": "Stop user on auth failure during Locust runs.",
        "recommended": "0",
    },
    {
        "key": "LOCUST_MAX_LOGIN_ATTEMPTS",
        "cast": "int",
        "default": 2,
        "description": "Max login retries before aborting.",
        "recommended": "2",
    },
    {
        "key": "LOCUST_USER_CREDENTIALS",
        "cast": "str",
        "default": None,
        "description": "JSON list of explicit username/password pairs.",
        "note": 'Example: [{"username":"user1","password":"pass"}]',
    },
]

# --- Load section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "load",
    "title": "Load Testing Inputs",
    "note": "Environment-driven knobs consumed by loadtests/locustfile.py.",
}
