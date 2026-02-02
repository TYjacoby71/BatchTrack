"""
Locust Load Testing Configuration - Production Mix

Uses production-weighted user classes and environment-driven credentials.
"""

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
from locust import HttpUser, task, between, events, SequentialTaskSet
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
LOCUST_ENABLE_BROWSE_USERS = _get_bool_env("LOCUST_ENABLE_BROWSE_USERS", False)


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


_sanitize_cli_args()


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


class AnonymousUser(HttpUser):
    """Anonymous user browsing public content only."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(4, 12)
    weight = 1

    @task(5)
    def view_homepage(self):
        """Load homepage."""
        self.client.get("/", name="homepage")

    @task(3)
    def view_tools_index(self):
        """Browse tools index page."""
        self.client.get("/tools", name="tools_index")

    @task(2)
    def view_global_items(self):
        """Browse global items library."""
        self.client.get("/global-items", name="global_items")

    @task(2)
    def search_public_global_items(self):
        """Exercise the public global item search endpoint."""
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        params = {"q": query, "type": "ingredient", "group": "ingredient"}
        self.client.get(
            "/api/public/global-items/search",
            params=params,
            name="public_global_item_search",
        )

    @task(1)
    def view_signup(self):
        """View signup page."""
        self.client.get("/auth/signup", name="signup_page")

    @task(1)
    def view_public_units(self):
        """Hit public units endpoint."""
        self.client.get("/api/public/units", name="public_units")


class AuthenticatedMixin:
    """Shared helpers for authenticated users."""

    login_username: str = ""
    login_password: str = ""
    csrf_token: Optional[str] = None

    def on_start(self):
        creds = _allocate_credentials()
        self.login_username = creds.get("username", "")
        self.login_password = creds.get("password", "")
        self._perform_login(self.login_username, self.login_password)

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
        response = self.client.get(path, name=f"csrf:{path}")
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

    def _perform_login(self, username: str, password: str):
        if not username or not password:
            self._log_login_failure("missing_credentials")
            return

        login_page = self.client.get("/auth/login", name="login_page")
        if login_page.status_code != 200:
            self._log_login_failure("login_page", login_page)
            return

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

    def _fetch_recipe_bootstrap(self):
        response = self.client.get("/api/bootstrap/recipes", name="bootstrap_recipes")
        if response.status_code != 200:
            return []
        payload = self._safe_json(response)
        if isinstance(payload, dict):
            return payload.get("recipes", [])
        return []

    def _fetch_product_bootstrap(self):
        response = self.client.get("/api/bootstrap/products", name="bootstrap_products")
        if response.status_code != 200:
            return {"products": [], "sku_inventory_ids": []}
        payload = self._safe_json(response)
        if isinstance(payload, dict):
            return payload
        return {"products": [], "sku_inventory_ids": []}

    def _fetch_ingredient_list(self):
        response = self.client.get("/api/ingredients", name="ingredients_list")
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


class RecipeOpsUser(BaseAuthenticatedUser):
    """Recipe planning + batch workflow."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(6, 14)
    weight = 4

    @task(7)
    def view_dashboard(self):
        self.client.get("/dashboard", name="dashboard")

    @task(6)
    def view_recipes_list(self):
        self.client.get("/recipes", name="recipes_list")

    @task(4)
    def view_recipe_detail(self):
        recipe_id = self._pick_id(self._get_recipe_ids())
        if not recipe_id:
            return
        self.client.get(f"/recipes/{recipe_id}/view", name="recipe_detail")

    @task(3)
    def view_batches_list(self):
        self.client.get("/batches", name="batches_list")

    @task(2)
    def view_global_items(self):
        self.client.get("/global-items", name="global_items")

    @task(2)
    def search_global_items(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        params = {"q": query, "type": "ingredient", "group": "ingredient"}
        self.client.get(
            "/api/ingredients/global-items/search",
            params=params,
            name="auth_global_item_search",
        )

    @task(1)
    def view_batch_available_ingredients(self):
        recipe_id = self._pick_id(self._get_recipe_ids())
        if not recipe_id:
            return
        self.client.get(
            f"/batches/api/available-ingredients/{recipe_id}",
            name="batch_available_ingredients",
        )


class InventoryOpsUser(BaseAuthenticatedUser):
    """Inventory browsing + ingredient lookup."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(6, 14)
    weight = 3

    @task(6)
    def view_inventory_list(self):
        self.client.get("/inventory", name="inventory_list")

    @task(5)
    def search_inventory(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        params = {"q": query, "type": "ingredient"}
        self.client.get(
            "/inventory/api/search",
            params=params,
            name="inventory_search",
        )

    @task(3)
    def view_inventory_item(self):
        item_id = self._pick_id(self._get_ingredient_ids())
        if not item_id:
            return
        self.client.get(
            f"/api/inventory/item/{item_id}",
            name="inventory_item_detail",
        )

    @task(3)
    def ingredient_categories(self):
        self.client.get("/api/ingredients/categories", name="ingredient_categories")

    @task(2)
    def ingredient_definition_search(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self.client.get(
            "/api/ingredients/ingredients/search",
            params={"q": query},
            name="ingredient_definition_search",
        )

    @task(2)
    def refresh_ingredient_list(self):
        self.client.get("/api/ingredients", name="ingredients_list")

    @task(1)
    def unit_converter(self):
        payload = {
            "from_amount": 1000,
            "from_unit": "g",
            "to_unit": "kg",
        }
        ingredient_id = self._pick_id(self._get_ingredient_ids())
        if ingredient_id:
            payload["ingredient_id"] = ingredient_id
        headers = self._csrf_headers(referer_path="/dashboard")
        self.client.post("/api/unit-converter", json=payload, headers=headers, name="unit_converter")


class ProductOpsUser(BaseAuthenticatedUser):
    """Product inventory + SKU management."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(6, 14)
    weight = 2

    @task(6)
    def view_products_list(self):
        self.client.get("/products", name="products_list")

    @task(4)
    def view_product_detail(self):
        product_id = self._pick_id(self._get_product_ids())
        if not product_id:
            return
        self.client.get(f"/products/{product_id}", name="product_detail")

    @task(3)
    def search_products(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self.client.get(
            "/api/products/search",
            params={"q": query},
            name="product_search",
        )

    @task(2)
    def low_stock_summary(self):
        self.client.get(
            "/api/products/low-stock",
            params={"threshold": 1.0},
            name="product_low_stock",
        )

    @task(2)
    def product_alerts(self):
        self.client.get("/products/alerts", name="product_alerts")

    @task(1)
    def product_stock_summary(self):
        self.client.get("/products/api/stock-summary", name="product_stock_summary")


class BatchWorkflowSequence(SequentialTaskSet):
    def on_start(self):
        self.milk_global_item_id = None
        self.milk_item_id = None
        self.custom_item_id = None
        self.recipe_id = None
        self._suffix = f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
        self._milk_item_name = f"Milk (Locust {self._suffix})"
        self._custom_item_name = f"Custom Pickle {self._suffix}"
        self._recipe_name = f"Locust Milk Pickle Recipe {self._suffix}"
        self._milk_unit = "gallon"
        self._pickle_unit = "count"

    def _require(self, value, label):
        if value:
            return value
        LOGGER.warning("Locust batch workflow missing %s", label)
        raise StopUser()

    def _restock_item(self, item_id: int, unit: str, name: str) -> None:
        token = self.user._ensure_csrf_token("/inventory")
        data = {
            "change_type": "restock",
            "quantity": "10",
            "input_unit": unit,
            "notes": "Locust restock",
        }
        if token:
            data["csrf_token"] = token
        headers = self.user._csrf_headers(referer_path="/inventory")
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Accept"] = "application/json"
        response = self.client.post(
            f"/inventory/adjust/{item_id}",
            data=data,
            headers=headers,
            name=name,
        )
        payload = self.user._safe_json(response)
        if response.status_code >= 400 or (payload and not payload.get("success", True)):
            LOGGER.warning("Locust restock failed (%s): %s", name, payload or response.text)
            raise StopUser()

    def _start_batch(self, request_name: str) -> int:
        payload = {
            "recipe_id": self.recipe_id,
            "scale": 1.0,
            "batch_type": "ingredient",
            "notes": "Locust batch workflow",
            "force_start": False,
        }
        headers = self.user._csrf_headers(referer_path="/batches")
        response = self.client.post(
            "/batches/api/start-batch",
            json=payload,
            headers=headers,
            name=request_name,
        )
        data = self.user._safe_json(response)
        if data and data.get("success") and data.get("batch_id"):
            return int(data["batch_id"])
        LOGGER.warning("Batch start failed: %s", data or response.text)
        raise StopUser()

    @task
    def browse_public_pages(self):
        self.client.get("/", name="homepage")
        self.client.get("/tools", name="tools_index")
        self.client.get("/global-items", name="global_items")
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self.client.get(
            "/api/public/global-items/search",
            params={"q": query, "type": "ingredient", "group": "ingredient"},
            name="public_global_item_search",
        )
        self.client.get("/auth/signup", name="signup_page")
        self.client.get("/api/public/units", name="public_units")

    @task
    def browse_authenticated_pages(self):
        self.client.get("/dashboard", name="dashboard")
        self.client.get("/recipes", name="recipes_list")
        self.client.get("/batches", name="batches_list")
        self.client.get("/inventory", name="inventory_list")
        self.client.get("/products", name="products_list")
        self.client.get("/global-items", name="global_items")

    @task
    def browse_search_endpoints(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self.client.get(
            "/api/ingredients/global-items/search",
            params={"q": query, "type": "ingredient", "group": "ingredient"},
            name="auth_global_item_search",
        )
        self.client.get(
            "/inventory/api/search",
            params={"q": query, "type": "ingredient"},
            name="inventory_search",
        )
        self.client.get("/api/ingredients/categories", name="ingredient_categories")
        self.client.get(
            "/api/ingredients/ingredients/search",
            params={"q": query},
            name="ingredient_definition_search",
        )
        self.client.get("/api/ingredients", name="ingredients_list")
        self.client.get(
            "/api/products/search",
            params={"q": query},
            name="product_search",
        )
        self.client.get(
            "/api/products/low-stock",
            params={"threshold": 1.0},
            name="product_low_stock",
        )
        self.client.get("/products/alerts", name="product_alerts")
        self.client.get("/products/api/stock-summary", name="product_stock_summary")

    @task
    def browse_detail_endpoints(self):
        recipe_ids = self.user._get_recipe_ids()
        product_ids = self.user._get_product_ids()
        ingredient_ids = self.user._get_ingredient_ids()

        recipe_id = self.user._pick_id(recipe_ids)
        if recipe_id:
            self.client.get(f"/recipes/{recipe_id}/view", name="recipe_detail")
            self.client.get(
                f"/batches/api/available-ingredients/{recipe_id}",
                name="batch_available_ingredients",
            )

        product_id = self.user._pick_id(product_ids)
        if product_id:
            self.client.get(f"/products/{product_id}", name="product_detail")

        ingredient_id = self.user._pick_id(ingredient_ids)
        if ingredient_id:
            self.client.get(
                f"/api/inventory/item/{ingredient_id}",
                name="inventory_item_detail",
            )

    @task
    def unit_converter(self):
        payload = {
            "from_amount": 1000,
            "from_unit": "g",
            "to_unit": "kg",
        }
        ingredient_id = self.user._pick_id(self.user._get_ingredient_ids())
        if ingredient_id:
            payload["ingredient_id"] = ingredient_id
        self.user._ensure_csrf_token("/dashboard")
        headers = self.user._csrf_headers(referer_path="/dashboard")
        self.client.post("/api/unit-converter", json=payload, headers=headers, name="unit_converter")

    @task
    def lookup_global_milk(self):
        response = self.client.get(
            "/api/ingredients/global-items/search",
            params={"q": "milk", "type": "ingredient", "group": "ingredient"},
            name="global_items_search_milk",
        )
        payload = self.user._safe_json(response)
        self.milk_global_item_id = _extract_global_item_id(payload)
        self._require(self.milk_global_item_id, "global milk item id")

    @task
    def create_global_milk_inventory(self):
        self._require(self.milk_global_item_id, "global milk item id")
        payload = {
            "name": self._milk_item_name,
            "type": "ingredient",
            "unit": self._milk_unit,
            "global_item_id": self.milk_global_item_id,
        }
        headers = self.user._csrf_headers(referer_path="/inventory")
        response = self.client.post(
            "/api/ingredients/ingredients/create-or-link",
            json=payload,
            headers=headers,
            name="create_global_milk_inventory",
        )
        data = self.user._safe_json(response)
        item = (data or {}).get("item") if isinstance(data, dict) else None
        self.milk_item_id = item.get("id") if isinstance(item, dict) else None
        self._require(self.milk_item_id, "milk inventory item id")

    @task
    def create_custom_pickle_inventory(self):
        payload = {
            "name": self._custom_item_name,
            "type": "ingredient",
            "unit": self._pickle_unit,
        }
        headers = self.user._csrf_headers(referer_path="/inventory")
        response = self.client.post(
            "/api/ingredients/ingredients/create-or-link",
            json=payload,
            headers=headers,
            name="create_custom_pickle_inventory",
        )
        data = self.user._safe_json(response)
        item = (data or {}).get("item") if isinstance(data, dict) else None
        self.custom_item_id = item.get("id") if isinstance(item, dict) else None
        self._require(self.custom_item_id, "custom pickle item id")

    @task
    def restock_milk_and_pickle(self):
        self._require(self.milk_item_id, "milk inventory item id")
        self._require(self.custom_item_id, "custom pickle item id")
        self._restock_item(self.milk_item_id, self._milk_unit, "restock_global_milk")
        self._restock_item(self.custom_item_id, self._pickle_unit, "restock_custom_pickle")

    @task
    def create_recipe(self):
        self._require(self.milk_global_item_id, "global milk item id")
        self._require(self.custom_item_id, "custom pickle item id")
        token = self.user._ensure_csrf_token("/recipes/new")
        form_data = [
            ("csrf_token", token or ""),
            ("name", self._recipe_name),
            ("instructions", "Locust recipe using milk + custom pickle"),
            ("predicted_yield", "1"),
            ("predicted_yield_unit", "count"),
            ("ingredient_ids[]", str(self.custom_item_id)),
            ("ingredient_ids[]", ""),
            ("global_item_ids[]", ""),
            ("global_item_ids[]", str(self.milk_global_item_id)),
            ("amounts[]", "1"),
            ("amounts[]", "1"),
            ("units[]", self._pickle_unit),
            ("units[]", self._milk_unit),
        ]
        headers = self.user._csrf_headers(referer_path="/recipes/new")
        response = self.client.post(
            "/recipes/new",
            data=form_data,
            headers=headers,
            allow_redirects=False,
            name="create_recipe",
        )
        location = response.headers.get("Location", "")
        match = re.search(r"/recipes/(\\d+)", location)
        self.recipe_id = int(match.group(1)) if match else None
        self._require(self.recipe_id, "recipe id")

    @task
    def view_created_recipe(self):
        self._require(self.recipe_id, "recipe id")
        self.client.get(f"/recipes/{self.recipe_id}/view", name="recipe_detail")
        self.client.get(
            f"/batches/api/available-ingredients/{self.recipe_id}",
            name="batch_available_ingredients",
        )

    @task
    def start_and_cancel_batch(self):
        self._require(self.recipe_id, "recipe id")
        batch_id = self._start_batch("start_batch_for_cancel")
        token = self.user._ensure_csrf_token("/batches")
        data = {"csrf_token": token} if token else {}
        headers = self.user._csrf_headers(referer_path=f"/batches/{batch_id}")
        response = self.client.post(
            f"/batches/cancel/{batch_id}",
            data=data,
            headers=headers,
            allow_redirects=False,
            name="cancel_batch",
        )
        if response.status_code >= 400:
            LOGGER.warning("Cancel batch failed: %s", response.text)
            raise StopUser()

    @task
    def start_and_fail_batch(self):
        self._require(self.recipe_id, "recipe id")
        batch_id = self._start_batch("start_batch_for_fail")
        headers = self.user._csrf_headers(referer_path=f"/batches/in-progress/{batch_id}")
        response = self.client.post(
            f"/batches/finish-batch/{batch_id}/fail",
            json={"reason": "Locust workflow failure"},
            headers=headers,
            name="fail_batch",
        )
        if response.status_code >= 400:
            LOGGER.warning("Fail batch failed: %s", response.text)
            raise StopUser()

    @task
    def start_and_complete_batch(self):
        self._require(self.recipe_id, "recipe id")
        batch_id = self._start_batch("start_batch_for_complete")
        token = self.user._ensure_csrf_token("/batches")
        data = {
            "output_type": "ingredient",
            "final_quantity": "1",
            "output_unit": "count",
        }
        if token:
            data["csrf_token"] = token
        headers = self.user._csrf_headers(referer_path=f"/batches/in-progress/{batch_id}")
        response = self.client.post(
            f"/batches/finish-batch/{batch_id}/complete",
            data=data,
            headers=headers,
            allow_redirects=False,
            name="complete_batch",
        )
        if response.status_code >= 400:
            LOGGER.warning("Complete batch failed: %s", response.text)
            raise StopUser()
        raise StopUser()


class BatchWorkflowUser(BaseAuthenticatedUser):
    wait_time = between(1, 3)
    tasks = [BatchWorkflowSequence]
    weight = 1


# Explicit user class list so Locust auto-distributes without CLI flags.
user_classes = [
    BatchWorkflowUser,
    RecipeOpsUser,
    InventoryOpsUser,
    ProductOpsUser,
    AnonymousUser,
]