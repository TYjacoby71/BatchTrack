"""
Shared helpers and configuration for load tests.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
from typing import Dict, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:  # Optional dependency on some runners
    BeautifulSoup = None

from gevent.lock import Semaphore
from locust import HttpUser, events
from locust.exception import StopUser

LOGGER = logging.getLogger(__name__)

GLOBAL_ITEM_SEARCH_TERMS = [
    "basil",
    "lavender",
    "peppermint",
    "powder",
    "oil",
    "butter",
    "clay",
    "extract",
]

_CSRF_INPUT_RE = re.compile(
    r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_CSRF_META_RE = re.compile(
    r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        LOGGER.warning("Invalid %s value %r, using %s", name, value, default)
        return default


LOCUST_USER_BASE = os.getenv("LOCUST_USER_BASE", "loadtest_user")
LOCUST_USER_PASSWORD = os.getenv("LOCUST_USER_PASSWORD", "loadtest123")
LOCUST_USER_COUNT = max(1, _get_int_env("LOCUST_USER_COUNT", 10000))
LOCUST_CACHE_TTL_SECONDS = max(0, _get_int_env("LOCUST_CACHE_TTL", 120))
LOCUST_REQUIRE_HTTPS = _get_bool_env("LOCUST_REQUIRE_HTTPS", True)
LOCUST_LOG_LOGIN_FAILURE_CONTEXT = _get_bool_env("LOCUST_LOG_LOGIN_FAILURE_CONTEXT", True)
LOCUST_ENABLE_BROWSE_USERS = _get_bool_env("LOCUST_ENABLE_BROWSE_USERS", True)
LOCUST_FAIL_FAST_LOGIN = _get_bool_env("LOCUST_FAIL_FAST_LOGIN", True)
LOCUST_ABORT_ON_AUTH_FAILURE = _get_bool_env("LOCUST_ABORT_ON_AUTH_FAILURE", False)
LOCUST_MAX_LOGIN_ATTEMPTS = max(1, _get_int_env("LOCUST_MAX_LOGIN_ATTEMPTS", 2))
LOCUST_DASHBOARD_PATH = os.getenv("LOCUST_DASHBOARD_PATH", "/user_dashboard")


def _sanitize_cli_args() -> None:
    """Drop empty CLI args before Locust parses positional user classes."""
    if not sys.argv:
        return
    cleaned_args = [sys.argv[0]]
    dropped = False
    for arg in sys.argv[1:]:
        if arg is None:
            dropped = True
            continue
        if isinstance(arg, str) and not arg.strip():
            dropped = True
            continue
        cleaned_args.append(arg)

    if dropped:
        LOGGER.warning(
            "Removed empty CLI arguments to avoid Locust 'Unknown User(s)' errors. "
            "Check any LOCUST_USER_CLASSES interpolation for empty values."
        )
        sys.argv[:] = cleaned_args


def _extract_global_item_id(payload) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    results = payload.get("results") or []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        forms = entry.get("forms") or []
        for form in forms:
            if isinstance(form, dict) and form.get("id"):
                return int(form["id"])
        if entry.get("id"):
            return int(entry["id"])
    return None


def _load_user_credentials():
    raw = (os.getenv("LOCUST_USER_CREDENTIALS") or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            LOGGER.warning("LOCUST_USER_CREDENTIALS invalid JSON: %s", exc)
        else:
            if isinstance(payload, list):
                cleaned = []
                for entry in payload:
                    if not isinstance(entry, dict):
                        continue
                    username = (entry.get("username") or "").strip()
                    password = (entry.get("password") or "").strip()
                    if username and password:
                        cleaned.append({"username": username, "password": password})
                if cleaned:
                    return cleaned
                LOGGER.warning("LOCUST_USER_CREDENTIALS provided but empty after cleanup.")
            else:
                LOGGER.warning("LOCUST_USER_CREDENTIALS must be a JSON list.")

    return [
        {"username": f"{LOCUST_USER_BASE}{i}", "password": LOCUST_USER_PASSWORD}
        for i in range(1, LOCUST_USER_COUNT + 1)
    ]


_CREDENTIAL_POOL = _load_user_credentials()
_CREDENTIAL_LOCK = Semaphore()
_CREDENTIAL_INDEX = 0


def _allocate_credentials() -> dict:
    global _CREDENTIAL_INDEX
    if not _CREDENTIAL_POOL:
        return {"username": "", "password": ""}
    with _CREDENTIAL_LOCK:
        credential = _CREDENTIAL_POOL[_CREDENTIAL_INDEX % len(_CREDENTIAL_POOL)]
        _CREDENTIAL_INDEX += 1
    return dict(credential)


class SharedCache:
    def __init__(self, name: str, default):
        self._name = name
        self._default = default
        self._value = None
        self._updated_at = 0.0
        self._lock = Semaphore()

    def get(self, loader):
        if LOCUST_CACHE_TTL_SECONDS <= 0:
            return self._refresh(loader)

        now = time.time()
        if self._value is not None and (now - self._updated_at) < LOCUST_CACHE_TTL_SECONDS:
            return self._value
        with self._lock:
            now = time.time()
            if self._value is not None and (now - self._updated_at) < LOCUST_CACHE_TTL_SECONDS:
                return self._value
            return self._refresh(loader)

    def _refresh(self, loader):
        try:
            value = loader()
        except Exception as exc:
            LOGGER.warning("Locust cache refresh failed for %s: %s", self._name, exc)
            if self._value is not None:
                return self._value
            return self._clone_default()

        if value is None:
            value = self._clone_default()
        self._value = value
        self._updated_at = time.time()
        return self._value

    def _clone_default(self):
        if isinstance(self._default, dict):
            return dict(self._default)
        if isinstance(self._default, list):
            return list(self._default)
        return self._default


_RECIPE_BOOTSTRAP_CACHE = SharedCache("recipe_bootstrap", [])
_PRODUCT_BOOTSTRAP_CACHE = SharedCache(
    "product_bootstrap", {"products": [], "sku_inventory_ids": []}
)
_INGREDIENT_LIST_CACHE = SharedCache("ingredient_list", [])


@events.test_start.add_listener
def _validate_locust_host(environment, **kwargs):
    if not LOCUST_REQUIRE_HTTPS:
        return
    host = (environment.host or "").strip()
    if not host:
        LOGGER.warning("LOCUST_REQUIRE_HTTPS=1 but no --host was provided.")
        return
    if not host.startswith("https://"):
        raise RuntimeError(
            "LOCUST_REQUIRE_HTTPS=1 requires an https:// host so Secure cookies persist."
        )


class AuthenticatedMixin:
    """Shared helpers for authenticated users."""

    login_username: str = ""
    login_password: str = ""
    csrf_token: Optional[str] = None
    is_authenticated: bool = False
    _login_failures: int = 0

    def on_start(self):
        creds = _allocate_credentials()
        self.login_username = creds.get("username", "")
        self.login_password = creds.get("password", "")
        self.is_authenticated = False
        self._login_failures = 0
        if not self._perform_login(self.login_username, self.login_password):
            if LOCUST_FAIL_FAST_LOGIN:
                raise StopUser()

    def _safe_json(self, response):
        try:
            return response.json()
        except ValueError:
            return None

    def _extract_csrf(self, response) -> Optional[str]:
        """Extract CSRF token from login page."""
        text = response.text or ""
        try:
            if BeautifulSoup is not None:
                soup = BeautifulSoup(text, "html.parser")

                token_field = soup.find("input", {"name": "csrf_token"})
                if token_field:
                    return token_field.get("value")

                meta_csrf = soup.find("meta", {"name": "csrf-token"})
                if meta_csrf:
                    return meta_csrf.get("content")

        except Exception:
            return None
        if text:
            match = _CSRF_INPUT_RE.search(text)
            if match:
                return match.group(1)
            match = _CSRF_META_RE.search(text)
            if match:
                return match.group(1)
        return None

    def _base_url(self) -> str:
        host = (getattr(self, "host", None) or "").strip()
        if host:
            return host.rstrip("/")
        return (getattr(self.client, "base_url", "") or "").rstrip("/")

    def _absolute_url(self, path: str) -> str:
        if not path:
            return self._base_url()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = self._base_url()
        if not base:
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    def _update_csrf_from_response(self, response) -> None:
        token = self._extract_csrf(response)
        if token:
            self.csrf_token = token

    def _ensure_csrf_token(self, path: str) -> Optional[str]:
        if self.csrf_token:
            return self.csrf_token
        response = self._authed_get(path, name=f"csrf:{path}")
        if response is None:
            return self.csrf_token
        self._update_csrf_from_response(response)
        return self.csrf_token

    def _csrf_headers(self, referer_path: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.csrf_token:
            headers["X-CSRFToken"] = self.csrf_token
        base_url = self._base_url()
        if base_url:
            headers["Origin"] = base_url
            if referer_path:
                headers["Referer"] = self._absolute_url(referer_path)
        return headers

    def _login_succeeded(self, response) -> bool:
        if response.status_code in {301, 302, 303, 307, 308}:
            location = (response.headers.get("Location") or "").lower()
            if location and "/auth/login" in location:
                return False
            return True
        if response.status_code != 200:
            return False
        response_url = (response.url or "").lower()
        if "/auth/login" in response_url:
            return False
        return True

    def _log_login_failure(self, stage: str, response=None, extra=None):
        if not LOCUST_LOG_LOGIN_FAILURE_CONTEXT:
            return
        context = {
            "stage": stage,
            "username": self.login_username,
        }
        if response is not None:
            context.update(
                {
                    "status": response.status_code,
                    "url": response.url,
                }
            )
            snippet = (response.text or "").strip()
            if snippet:
                context["body_snippet"] = snippet[:200]
        if extra:
            context.update(extra)
        LOGGER.warning("Locust login failed: %s", context)

    def _record_auth_failure(self):
        self.is_authenticated = False
        self._login_failures += 1

    def _can_retry_login(self) -> bool:
        return self._login_failures < LOCUST_MAX_LOGIN_ATTEMPTS

    def _ensure_authenticated(self) -> bool:
        if self.is_authenticated:
            return True
        if not self._can_retry_login():
            return False
        return self._perform_login(self.login_username, self.login_password)

    def _is_auth_failure_response(self, response) -> bool:
        if response is None:
            return False
        if response.status_code in {401, 403}:
            return True
        if response.status_code in {301, 302, 303, 307, 308}:
            location = (response.headers.get("Location") or "").lower()
            if "/auth/login" in location:
                return True
        response_url = (response.url or "").lower()
        if "/auth/login" in response_url:
            return True
        return False

    def _handle_auth_failure(self, response, request_name: Optional[str] = None) -> bool:
        if not self._is_auth_failure_response(response):
            return False
        self._record_auth_failure()
        if LOCUST_ABORT_ON_AUTH_FAILURE:
            extra = {"request": request_name} if request_name else None
            self._log_login_failure("auth_failure", response, extra=extra)
            raise StopUser()
        return True

    def _authed_get(self, path: str, **kwargs):
        if not self._ensure_authenticated():
            return None
        response = self.client.get(path, **kwargs)
        self._handle_auth_failure(response, kwargs.get("name"))
        return response

    def _authed_post(self, path: str, **kwargs):
        if not self._ensure_authenticated():
            return None
        response = self.client.post(path, **kwargs)
        self._handle_auth_failure(response, kwargs.get("name"))
        return response

    def _perform_login(self, username: str, password: str) -> bool:
        if not username or not password:
            self._log_login_failure("missing_credentials")
            self._record_auth_failure()
            return False

        login_page = self.client.get("/auth/login", name="login_page")
        if login_page.status_code != 200:
            self._log_login_failure("login_page", login_page)
            self._record_auth_failure()
            return False

        self._update_csrf_from_response(login_page)
        token = self.csrf_token or self._extract_csrf(login_page)

        payload = {
            "username": username,
            "password": password,
            "form_type": "login",
        }
        if token:
            payload["csrf_token"] = token

        referer_url = self._absolute_url("/auth/login")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": referer_url,
        }
        origin = self._base_url()
        if origin:
            headers["Origin"] = origin

        response = self.client.post(
            "/auth/login",
            data=payload,
            headers=headers,
            name="login_submit",
            allow_redirects=False,
        )
        self._update_csrf_from_response(response)
        if not self._login_succeeded(response):
            self._log_login_failure("login_submit", response)
            self._record_auth_failure()
            return False
        self.is_authenticated = True
        self._login_failures = 0
        return True

    def _fetch_recipe_bootstrap(self):
        response = self._authed_get("/api/bootstrap/recipes", name="bootstrap_recipes")
        if response is None:
            return []
        if response.status_code != 200:
            return []
        payload = self._safe_json(response)
        if isinstance(payload, dict):
            return payload.get("recipes", [])
        return []

    def _fetch_product_bootstrap(self):
        response = self._authed_get("/api/bootstrap/products", name="bootstrap_products")
        if response is None:
            return {"products": [], "sku_inventory_ids": []}
        if response.status_code != 200:
            return {"products": [], "sku_inventory_ids": []}
        payload = self._safe_json(response)
        if isinstance(payload, dict):
            return payload
        return {"products": [], "sku_inventory_ids": []}

    def _fetch_ingredient_list(self):
        response = self._authed_get("/api/ingredients", name="ingredients_list")
        if response is None:
            return []
        if response.status_code != 200:
            return []
        payload = self._safe_json(response)
        if isinstance(payload, list):
            return payload
        return []

    def _get_recipe_ids(self):
        recipes = _RECIPE_BOOTSTRAP_CACHE.get(self._fetch_recipe_bootstrap)
        return [
            recipe.get("id")
            for recipe in recipes
            if isinstance(recipe, dict) and recipe.get("id")
        ]

    def _get_product_ids(self):
        payload = _PRODUCT_BOOTSTRAP_CACHE.get(self._fetch_product_bootstrap)
        if not isinstance(payload, dict):
            return []
        products = payload.get("products", [])
        return [
            product.get("id")
            for product in products
            if isinstance(product, dict) and product.get("id")
        ]

    def _get_ingredient_ids(self):
        ingredients = _INGREDIENT_LIST_CACHE.get(self._fetch_ingredient_list)
        return [
            ingredient.get("id")
            for ingredient in ingredients
            if isinstance(ingredient, dict) and ingredient.get("id")
        ]

    def _pick_id(self, ids):
        return random.choice(ids) if ids else None


class BaseAuthenticatedUser(AuthenticatedMixin, HttpUser):
    abstract = True
