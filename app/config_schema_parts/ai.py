"""Config schema: AI and BatchBot settings.

Synopsis:
Defines Gemini API and BatchBot quota configuration keys.

Glossary:
- BatchBot: AI assistant for recipes and operations.
"""

# --- AI fields ---
# Purpose: Provide AI model and quota configuration definitions.
FIELDS = [
    {
        "key": "GOOGLE_AI_API_KEY",
        "cast": "str",
        "default": None,
        "description": "Gemini API key used by BatchBot.",
        "secret": True,
    },
    {
        "key": "GOOGLE_AI_DEFAULT_MODEL",
        "cast": "str",
        "default": "gemini-1.5-flash",
        "description": "Fallback Gemini model.",
        "recommended": "gemini-1.5-flash",
    },
    {
        "key": "GOOGLE_AI_BATCHBOT_MODEL",
        "cast": "str",
        "default": None,
        "description": "Model used by the paid BatchBot.",
        "recommended": "gemini-1.5-pro",
    },
    {
        "key": "GOOGLE_AI_PUBLICBOT_MODEL",
        "cast": "str",
        "default": "gemini-1.5-flash",
        "description": "Model used by the public help bot.",
        "recommended": "gemini-1.5-flash",
    },
    {
        "key": "GOOGLE_AI_ENABLE_SEARCH",
        "cast": "bool",
        "default": True,
        "description": "Enable Google Search grounding for prompts.",
        "recommended": "true",
    },
    {
        "key": "GOOGLE_AI_ENABLE_FILE_SEARCH",
        "cast": "bool",
        "default": True,
        "description": "Enable file search for prompts.",
        "recommended": "true",
    },
    {
        "key": "GOOGLE_AI_SEARCH_TOOL",
        "cast": "str",
        "default": "google_search",
        "description": "Search tool identifier.",
        "recommended": "google_search",
    },
    {
        "key": "BATCHBOT_REQUEST_TIMEOUT_SECONDS",
        "cast": "int",
        "default": 45,
        "description": "BatchBot request timeout.",
        "recommended": "45",
    },
    {
        "key": "BATCHBOT_DEFAULT_MAX_REQUESTS",
        "cast": "int",
        "default": 0,
        "description": "Base allowance per org per window.",
        "recommended": "0",
    },
    {
        "key": "BATCHBOT_REQUEST_WINDOW_DAYS",
        "cast": "int",
        "default": 30,
        "description": "BatchBot usage window length.",
        "recommended": "30",
    },
    {
        "key": "BATCHBOT_CHAT_MAX_MESSAGES",
        "cast": "int",
        "default": 60,
        "description": "Max chat-only prompts per window.",
        "recommended": "60",
    },
    {
        "key": "BATCHBOT_COST_PER_MILLION_INPUT",
        "cast": "float",
        "default": 0.35,
        "description": "Reference cost for inbound tokens (USD).",
        "recommended": "0.35",
    },
    {
        "key": "BATCHBOT_COST_PER_MILLION_OUTPUT",
        "cast": "float",
        "default": 0.53,
        "description": "Reference cost for outbound tokens (USD).",
        "recommended": "0.53",
    },
    {
        "key": "BATCHBOT_SIGNUP_BONUS_REQUESTS",
        "cast": "int",
        "default": 20,
        "description": "Bonus requests granted at signup.",
        "recommended": "20",
    },
    {
        "key": "BATCHBOT_REFILL_LOOKUP_KEY",
        "cast": "str",
        "default": "batchbot_refill_100",
        "description": "Stripe lookup key for BatchBot refills.",
        "recommended": "batchbot_refill_100",
    },
]

# --- AI section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "ai",
    "title": "AI Studio & BatchBot",
    "note": "Controls BatchBot models and quotas.",
}
