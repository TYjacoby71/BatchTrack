"""
Locust Load Testing Configuration - Production Mix

Uses production-weighted user classes and environment-driven credentials.
"""

import json
import logging
import os
import random
import time
from typing import Optional

from bs4 import BeautifulSoup
from gevent.lock import Semaphore
from locust import HttpUser, task, between, events

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
        try:
            soup = BeautifulSoup(response.text, "html.parser")

            token_field = soup.find("input", {"name": "csrf_token"})
            if token_field:
                return token_field.get("value")

            meta_csrf = soup.find("meta", {"name": "csrf-token"})
            if meta_csrf:
                return meta_csrf.get("content")

        except Exception:
            return None
        return None

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

        token = self._extract_csrf(login_page)

        payload = {
            "username": username,
            "password": password,
        }
        if token:
            payload["csrf_token"] = token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "/auth/login",
        }

        response = self.client.post(
            "/auth/login",
            data=payload,
            headers=headers,
            name="login_submit",
            allow_redirects=False,
        )
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
        self.client.post("/api/unit-converter", json=payload, name="unit_converter")


class ProductOpsUser(BaseAuthenticatedUser):
    """Product inventory + SKU management."""

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


# Explicit user class list so Locust auto-distributes without CLI flags.
user_classes = [
    RecipeOpsUser,
    InventoryOpsUser,
    ProductOpsUser,
    AnonymousUser,
]